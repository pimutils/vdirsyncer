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
extern crate quick_xml;
extern crate url;
extern crate chrono;
extern crate env_logger;

mod item;
mod storage;
pub mod errors;

pub mod exports {
    use std::ffi::CStr;
    use std::os::raw::c_char;

    pub use super::item::exports::*;
    pub use super::storage::exports::*;

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_free_str(s: *const c_char) {
        CStr::from_ptr(s);
    }

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_init_logger() {
        ::env_logger::init();
    }
}
