#![cfg_attr(feature = "cargo-clippy", allow(single_match))]

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
extern crate base64;
extern crate chrono;
extern crate env_logger;
extern crate glob;
extern crate lazy_init;
extern crate quick_xml;
extern crate reqwest;
extern crate sha2;
extern crate shellexpand;
extern crate url;

#[macro_use]
extern crate serde_derive;
extern crate serde;
extern crate serde_json;

pub mod errors;
mod item;
mod storage;

pub mod exports {
    use std::ffi::CString;
    use std::os::raw::c_char;

    pub use super::item::exports::*;
    pub use super::storage::exports::*;

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_free_str(s: *mut c_char) {
        let _ = CString::from_raw(s);
    }

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_init_logger() {
        ::env_logger::init();
    }
}
