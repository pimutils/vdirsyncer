extern crate atomicwrites;
#[macro_use]
extern crate failure;
#[macro_use]
extern crate shippai;
extern crate libc;
extern crate uuid;
extern crate vobject;
#[macro_use]
extern crate log;
extern crate reqwest;
extern crate sha2;

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
