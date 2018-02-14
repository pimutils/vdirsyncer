extern crate cbindgen;

use std::env;
use std::fs::{remove_file, File};
use std::io::Write;
use std::path::Path;

const TEMPLATE_EACH: &'static str = r#"
#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_{name}_list(
    storage: *mut {path},
    err: *mut VdirsyncerError
) -> *mut VdirsyncerStorageListing {
    match (*storage).list() {
        Ok(x) => Box::into_raw(Box::new(VdirsyncerStorageListing {
            iterator: x,
            href: None,
            etag: None
        })),
        Err(e) => {
            e.fill_c_err(err);
            mem::zeroed()
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_{name}_get(
    storage: *mut {path},
    c_href: *const c_char,
    err: *mut VdirsyncerError
) -> *mut VdirsyncerStorageGetResult {
    let href = CStr::from_ptr(c_href);
    match (*storage).get(href.to_str().unwrap()) {
        Ok((item, href)) => {
            Box::into_raw(Box::new(VdirsyncerStorageGetResult {
                item: Box::into_raw(Box::new(item)),
                etag: CString::new(href).unwrap().into_raw()
            }))
        },
        Err(e) => {
            e.fill_c_err(err);
            mem::zeroed()
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_{name}_upload(
    storage: *mut {path},
    item: *mut Item,
    err: *mut VdirsyncerError
) -> *mut VdirsyncerStorageUploadResult {
    match (*storage).upload((*item).clone()) {
        Ok((href, etag)) => {
            Box::into_raw(Box::new(VdirsyncerStorageUploadResult {
                href: CString::new(href).unwrap().into_raw(),
                etag: CString::new(etag).unwrap().into_raw()
            }))
        },
        Err(e) => {
            e.fill_c_err(err);
            mem::zeroed()
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_{name}_update(
    storage: *mut {path},
    c_href: *const c_char,
    item: *mut Item,
    c_etag: *const c_char,
    err: *mut VdirsyncerError
) -> *const c_char {
    let href = CStr::from_ptr(c_href);
    let etag = CStr::from_ptr(c_etag);
    match (*storage).update(href.to_str().unwrap(), (*item).clone(), etag.to_str().unwrap()) {
        Ok(etag) => CString::new(etag).unwrap().into_raw(),
        Err(e) => {
            e.fill_c_err(err);
            mem::zeroed()
        }

    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_{name}_delete(
    storage: *mut {path},
    c_href: *const c_char,
    c_etag: *const c_char,
    err: *mut VdirsyncerError
) {
    let href = CStr::from_ptr(c_href);
    let etag = CStr::from_ptr(c_etag);
    match (*storage).delete(href.to_str().unwrap(), etag.to_str().unwrap()) {
        Ok(()) => (),
        Err(e) => e.fill_c_err(err)
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_{name}_buffered(storage: *mut {path}) {
    (*storage).buffered();
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_{name}_flush(
    storage: *mut {path},
    err: *mut VdirsyncerError
) {
    match (*storage).flush() {
        Ok(_) => (),
        Err(e) => e.fill_c_err(err)
    }
}
"#;

fn export_storage(f: &mut File, name: &str, path: &str) {
    // String formatting in rust is at compile time. That doesn't work well for our case.
    write!(
        f,
        "{}",
        TEMPLATE_EACH
            .replace("{name}", name)
            .replace("{path}", path)
    ).unwrap();
}

fn main() {
    let crate_dir = env::var("CARGO_MANIFEST_DIR").unwrap();

    let mut f = File::create(Path::new(&crate_dir).join("src/storage/exports.rs")).unwrap();
    write!(f, "// Auto-generated, do not check in.\n").unwrap();
    write!(f, "use std::os::raw::c_char;\n").unwrap();
    write!(f, "use std::mem;\n").unwrap();
    write!(f, "use std::ffi::{{CStr, CString}};\n").unwrap();
    write!(f, "use errors::*;\n").unwrap();
    write!(f, "use item::Item;\n").unwrap();
    write!(f, "use super::VdirsyncerStorageListing;\n").unwrap();
    write!(f, "use super::VdirsyncerStorageGetResult;\n").unwrap();
    write!(f, "use super::VdirsyncerStorageUploadResult;\n").unwrap();
    write!(f, "use super::Storage;\n").unwrap();

    write!(f, "use super::singlefile;\n").unwrap();
    export_storage(&mut f, "singlefile", "singlefile::SinglefileStorage");
    drop(f);

    let _ = remove_file(Path::new(&crate_dir).join("target/vdirsyncer_rustext.h"));

    let res = cbindgen::Builder::new()
        .with_crate(crate_dir)
        .with_language(cbindgen::Language::C)
        .generate();

    match res {
        Ok(x) => x.write_to_file("target/vdirsyncer_rustext.h"),
        Err(e) => println!("FAILED TO GENERATE BINDINGS: {:?}", e),
    }
}
