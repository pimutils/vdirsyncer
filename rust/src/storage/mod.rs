pub mod singlefile;
pub mod exports;
use std::ffi::CString;
use std::os::raw::c_char;
use errors::*;
use item::Item;

type ItemAndEtag = (Item, String);

pub trait Storage: Sized {
    /// returns an iterator of `(href, etag)`
    fn list<'a>(&'a mut self) -> Result<Box<Iterator<Item = (String, String)> + 'a>>;

    ///Fetch a single item.
    ///
    ///:param href: href to fetch
    ///:returns: (item, etag)
    ///:raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` if item can't be found.
    fn get(&mut self, href: &str) -> Result<ItemAndEtag>;

    /// Fetch multiple items. Duplicate hrefs must be ignored.
    ///
    /// Functionally similar to `get`, but might bring performance benefits on some storages when
    /// used cleverly.
    ///
    /// # Parameters
    /// - `hrefs`: list of hrefs to fetch
    /// - returns an iterator of `(href, item, etag)`
    fn get_multi<'a, I: Iterator<Item = String> + 'a>(
        &'a mut self,
        hrefs: I,
    ) -> Box<Iterator<Item = (String, Result<ItemAndEtag>)> + 'a> {
        Box::new(DefaultGetMultiIterator {
            storage: self,
            href_iter: hrefs,
        })
    }

    /// Upload a new item.
    ///
    /// In cases where the new etag cannot be atomically determined (i.e. in the same
    /// "transaction" as the upload itself), this method may return `None` as etag. This
    /// special case only exists because of DAV. Avoid this situation whenever possible.
    ///
    /// Returns `(href, etag)`
    fn upload(&mut self, item: Item) -> Result<(String, String)>;

    /// Update an item.
    ///
    /// The etag may be none in some cases, see `upload`.
    ///
    /// Returns `etag`
    fn update(&mut self, href: &str, item: Item, etag: &str) -> Result<String>;

    /// Delete an item by href.
    fn delete(&mut self, href: &str, etag: &str) -> Result<()>;

    /// Enter buffered mode for storages that support it.
    ///
    /// Uploads, updates and deletions may not be effective until `flush` is explicitly called.
    ///
    /// Use this if you will potentially write a lot of data to the storage, it improves
    /// performance for storages that implement it.
    fn buffered(&mut self) {}

    /// Write back all changes to the collection.
    fn flush(&mut self) -> Result<()> {
        Ok(())
    }
}

struct DefaultGetMultiIterator<'a, S: Storage + 'a, I: Iterator<Item = String>> {
    storage: &'a mut S,
    href_iter: I,
}

impl<'a, S, I> Iterator for DefaultGetMultiIterator<'a, S, I>
where
    S: Storage,
    I: Iterator<Item = String>,
{
    type Item = (String, Result<ItemAndEtag>);

    fn next(&mut self) -> Option<Self::Item> {
        match self.href_iter.next() {
            Some(x) => Some((x.to_owned(), self.storage.get(&x))),
            None => None,
        }
    }
}

pub struct VdirsyncerStorageListing {
    iterator: Box<Iterator<Item = (String, String)>>,
    href: Option<String>,
    etag: Option<String>,
}

impl VdirsyncerStorageListing {
    pub fn advance(&mut self) -> bool {
        match self.iterator.next() {
            Some((href, etag)) => {
                self.href = Some(href);
                self.etag = Some(etag);
                true
            }
            None => {
                self.href = None;
                self.etag = None;
                false
            }
        }
    }

    pub fn get_href(&mut self) -> Option<String> {
        self.href.take()
    }
    pub fn get_etag(&mut self) -> Option<String> {
        self.etag.take()
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_free_storage_listing(listing: *mut VdirsyncerStorageListing) {
    let _: Box<VdirsyncerStorageListing> = Box::from_raw(listing);
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_advance_storage_listing(
    listing: *mut VdirsyncerStorageListing,
) -> bool {
    (*listing).advance()
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_storage_listing_get_href(
    listing: *mut VdirsyncerStorageListing,
) -> *const c_char {
    CString::new((*listing).get_href().unwrap())
        .unwrap()
        .into_raw()
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_storage_listing_get_etag(
    listing: *mut VdirsyncerStorageListing,
) -> *const c_char {
    CString::new((*listing).get_etag().unwrap())
        .unwrap()
        .into_raw()
}

#[repr(C)]
pub struct VdirsyncerStorageGetResult {
    pub item: *mut Item,
    pub etag: *const c_char,
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_free_storage_get_result(res: *mut VdirsyncerStorageGetResult) {
    let _: Box<VdirsyncerStorageGetResult> = Box::from_raw(res);
}

#[repr(C)]
pub struct VdirsyncerStorageUploadResult {
    pub href: *const c_char,
    pub etag: *const c_char,
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_free_storage_upload_result(
    res: *mut VdirsyncerStorageUploadResult,
) {
    let _: Box<VdirsyncerStorageUploadResult> = Box::from_raw(res);
}
