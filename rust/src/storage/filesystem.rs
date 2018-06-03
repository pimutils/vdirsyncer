use super::Storage;
use errors::*;
use failure;
use libc;
use std::fs;
use std::io;
use std::io::{Read, Write};
use std::os::unix::fs::MetadataExt;
use std::path::{Path, PathBuf};
use std::process::Command;

use super::utils;

use item::Item;

use atomicwrites::{AllowOverwrite, AtomicFile, DisallowOverwrite};

pub struct FilesystemStorage {
    path: PathBuf,
    fileext: String,
    post_hook: Option<String>,
}

impl FilesystemStorage {
    pub fn new<P: AsRef<Path>>(path: P, fileext: &str, post_hook: Option<String>) -> Self {
        FilesystemStorage {
            path: path.as_ref().to_owned(),
            fileext: fileext.into(),
            post_hook,
        }
    }

    fn get_href(&self, ident: Option<&str>) -> String {
        let href_base = match ident {
            Some(x) => utils::generate_href(x),
            None => utils::random_href(),
        };
        format!("{}{}", href_base, self.fileext)
    }

    fn get_filepath(&self, href: &str) -> PathBuf {
        self.path.join(href)
    }

    fn run_post_hook<S: AsRef<::std::ffi::OsStr>>(&self, fpath: S) {
        if let Some(ref cmd) = self.post_hook {
            let status = match Command::new(cmd).arg(fpath).status() {
                Ok(x) => x,
                Err(e) => {
                    warn!("Failed to run external hook: {}", e);
                    return;
                }
            };

            if !status.success() {
                if let Some(code) = status.code() {
                    warn!("External hook exited with error code {}.", code);
                } else {
                    warn!("External hook was killed.");
                }
            }
        }
    }
}

#[inline]
fn handle_io_error(href: &str, e: io::Error) -> failure::Error {
    match e.kind() {
        io::ErrorKind::NotFound => Error::ItemNotFound {
            href: href.to_owned(),
        }.into(),
        io::ErrorKind::AlreadyExists => Error::ItemAlreadyExisting {
            href: href.to_owned(),
        }.into(),
        _ => e.into(),
    }
}

pub mod exports {
    use super::*;
    use std::ffi::CStr;
    use std::os::raw::c_char;

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_init_filesystem(
        path: *const c_char,
        fileext: *const c_char,
        post_hook: *const c_char,
    ) -> *mut Box<Storage> {
        let path_c = CStr::from_ptr(path);
        let fileext_c = CStr::from_ptr(fileext);
        let post_hook_c = CStr::from_ptr(post_hook);
        let post_hook_str = post_hook_c.to_str().unwrap();

        Box::into_raw(Box::new(Box::new(FilesystemStorage::new(
            path_c.to_str().unwrap(),
            fileext_c.to_str().unwrap(),
            if post_hook_str.is_empty() {
                None
            } else {
                Some(post_hook_str.to_owned())
            },
        ))))
    }
}

#[inline]
fn etag_from_file(metadata: &fs::Metadata) -> String {
    format!(
        "{}.{};{}",
        metadata.mtime(),
        metadata.mtime_nsec(),
        metadata.ino()
    )
}

impl Storage for FilesystemStorage {
    fn list<'a>(&'a mut self) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        let mut rv: Vec<(String, String)> = vec![];

        for entry_res in fs::read_dir(&self.path)? {
            let entry = entry_res?;
            let metadata = entry.metadata()?;

            if !metadata.is_file() {
                continue;
            }

            let fname: String = match entry.file_name().into_string() {
                Ok(x) => x,
                Err(_) => continue,
            };

            if !fname.ends_with(&self.fileext) {
                continue;
            }

            rv.push((fname, etag_from_file(&metadata)));
        }

        Ok(Box::new(rv.into_iter()))
    }

    fn get(&mut self, href: &str) -> Fallible<(Item, String)> {
        let fpath = self.get_filepath(href);
        let mut f = match fs::File::open(fpath) {
            Ok(x) => x,
            Err(e) => Err(handle_io_error(href, e))?,
        };

        let mut s = String::new();
        f.read_to_string(&mut s)?;
        Ok((Item::from_raw(s), etag_from_file(&f.metadata()?)))
    }

    fn upload(&mut self, item: Item) -> Fallible<(String, String)> {
        #[inline]
        fn inner(s: &mut FilesystemStorage, item: &Item, href: &str) -> io::Result<String> {
            let filepath = s.get_filepath(href);
            let af = AtomicFile::new(&filepath, DisallowOverwrite);
            let content = item.get_raw();
            af.write(|f| f.write_all(content.as_bytes()))?;
            let new_etag = etag_from_file(&fs::metadata(&filepath)?);
            s.run_post_hook(filepath);
            Ok(new_etag)
        }

        let ident = item.get_ident()?;
        let mut href = self.get_href(Some(&ident));
        let etag = match inner(self, &item, &href) {
            Ok(x) => x,
            Err(ref e) if e.raw_os_error() == Some(libc::ENAMETOOLONG) => {
                href = self.get_href(None);
                match inner(self, &item, &href) {
                    Ok(x) => x,
                    Err(e) => Err(handle_io_error(&href, e))?,
                }
            }
            Err(e) => Err(handle_io_error(&href, e))?,
        };

        Ok((href, etag))
    }

    fn update(&mut self, href: &str, item: Item, etag: &str) -> Fallible<String> {
        let filepath = self.get_filepath(href);
        let metadata = match fs::metadata(&filepath) {
            Ok(x) => x,
            Err(e) => Err(handle_io_error(href, e))?,
        };
        let actual_etag = etag_from_file(&metadata);
        if actual_etag != etag {
            Err(Error::WrongEtag {
                href: href.to_owned(),
            })?;
        }

        let af = AtomicFile::new(&filepath, AllowOverwrite);
        let content = item.get_raw();
        af.write(|f| f.write_all(content.as_bytes()))?;
        let new_etag = etag_from_file(&fs::metadata(filepath)?);
        Ok(new_etag)
    }

    fn delete(&mut self, href: &str, etag: &str) -> Fallible<()> {
        let filepath = self.get_filepath(href);
        let metadata = match fs::metadata(&filepath) {
            Ok(x) => x,
            Err(e) => Err(handle_io_error(href, e))?,
        };
        let actual_etag = etag_from_file(&metadata);
        if actual_etag != etag {
            Err(Error::WrongEtag {
                href: href.to_owned(),
            })?;
        }
        fs::remove_file(filepath)?;
        Ok(())
    }
}
