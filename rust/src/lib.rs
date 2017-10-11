extern crate vobject;
extern crate ring;

use std::ffi::CStr;
use std::os::raw::c_char;

pub mod item;

#[repr(C)]
pub struct VdirsyncerError {
    pub failed: bool,
    pub msg: *mut c_char,
}


#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_free_str(s: *const c_char) {
    CStr::from_ptr(s);
}
