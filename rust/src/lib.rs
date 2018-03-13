extern crate atomicwrites;
#[macro_use]
extern crate failure;
#[macro_use]
extern crate shippai;
extern crate ring;
extern crate vobject;
extern crate uuid;
extern crate libc;
#[macro_use] extern crate log;

mod item;
mod storage;
mod errors;

pub mod exports {
    use std::ffi::CStr;
    use std::os::raw::c_char;

    pub use super::item::exports::*;
    pub use super::storage::exports::*;
    pub use super::errors::exports::*;

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_free_str(s: *const c_char) {
        CStr::from_ptr(s);
    }
}
