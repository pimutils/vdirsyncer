pub use super::dav::exports::*;
pub use super::filesystem::exports::*;
pub use super::http::exports::*;
pub use super::singlefile::exports::*;
use super::Storage;
use errors::*;
use item::Item;
use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use std::ptr;

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_storage_free(storage: *mut Box<Storage>) {
    let _: Box<Box<Storage>> = Box::from_raw(storage);
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_storage_list(
    storage: *mut Box<Storage>,
    err: *mut *mut ShippaiError,
) -> *mut VdirsyncerStorageListing {
    if let Some(x) = export_result((**storage).list(), err) {
        Box::into_raw(Box::new(VdirsyncerStorageListing {
            iterator: x,
            href: None,
            etag: None,
        }))
    } else {
        ptr::null_mut()
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_storage_get(
    storage: *mut Box<Storage>,
    c_href: *const c_char,
    err: *mut *mut ShippaiError,
) -> *mut VdirsyncerStorageGetResult {
    let href = CStr::from_ptr(c_href);
    if let Some((item, href)) = export_result((**storage).get(href.to_str().unwrap()), err) {
        Box::into_raw(Box::new(VdirsyncerStorageGetResult {
            item: Box::into_raw(Box::new(item)),
            etag: CString::new(href).unwrap().into_raw(),
        }))
    } else {
        ptr::null_mut()
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_storage_upload(
    storage: *mut Box<Storage>,
    item: *mut Item,
    err: *mut *mut ShippaiError,
) -> *mut VdirsyncerStorageUploadResult {
    if let Some((href, etag)) = export_result((**storage).upload((*item).clone()), err) {
        Box::into_raw(Box::new(VdirsyncerStorageUploadResult {
            href: CString::new(href).unwrap().into_raw(),
            etag: CString::new(etag).unwrap().into_raw(),
        }))
    } else {
        ptr::null_mut()
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_storage_update(
    storage: *mut Box<Storage>,
    c_href: *const c_char,
    item: *mut Item,
    c_etag: *const c_char,
    err: *mut *mut ShippaiError,
) -> *const c_char {
    let href = CStr::from_ptr(c_href);
    let etag = CStr::from_ptr(c_etag);
    let res = (**storage).update(
        href.to_str().unwrap(),
        (*item).clone(),
        etag.to_str().unwrap(),
    );
    if let Some(etag) = export_result(res, err) {
        CString::new(etag).unwrap().into_raw()
    } else {
        ptr::null_mut()
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_storage_delete(
    storage: *mut Box<Storage>,
    c_href: *const c_char,
    c_etag: *const c_char,
    err: *mut *mut ShippaiError,
) {
    let href = CStr::from_ptr(c_href);
    let etag = CStr::from_ptr(c_etag);
    let res = (**storage).delete(href.to_str().unwrap(), etag.to_str().unwrap());
    let _ = export_result(res, err);
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_storage_buffered(storage: *mut Box<Storage>) {
    (**storage).buffered();
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_storage_flush(
    storage: *mut Box<Storage>,
    err: *mut *mut ShippaiError,
) {
    let _ = export_result((**storage).flush(), err);
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
