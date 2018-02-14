extern crate atomicwrites;
#[macro_use]
extern crate error_chain;
extern crate ring;
extern crate vobject;

pub mod item;
pub mod storage;

mod errors {
    use std::ffi::CString;
    use std::os::raw::c_char;
    use vobject;
    use atomicwrites;

    error_chain!{
        links {
            Vobject(vobject::error::VObjectError, vobject::error::VObjectErrorKind);
        }

        foreign_links {
            Io(::std::io::Error);
        }

        errors {
            ItemUnparseable {
                description("ItemUnparseable: The item cannot be parsed."),
                display("The item cannot be parsed."),
            }

            VobjectVersionMismatch(first: String, second: String) {
                description("Incompatible vobject versions."),
                display("Conflict between {} and {}", first, second),
            }

            UnexpectedVobject(found: String, expected: String) {
                description("Unexpected component type"),
                display("Found type {}, expected {}", found, expected),
            }

            ItemNotFound(href: String) {
                description("ItemNotFound: The item could not be found"),
                display("The item '{}' could not be found", href),
            }

            AlreadyExisting(href: String) {
                description("AlreadyExisting: An item at this href already exists"),
                display("The href '{}' is already taken", href),
            }

            WrongEtag(href: String) {
                description("WrongEtag: A wrong etag was provided."),
                display("A wrong etag for '{}' was provided. This indicates that two clients are writing data at the same time.", href),
            }

            MtimeMismatch(filepath: String) {
                description("MtimeMismatch: Two programs access the same file."),
                display("The mtime of {} has unexpectedly changed. Please close other programs accessing this file.", filepath),
            }
        }
    }

    impl From<atomicwrites::Error<Error>> for Error {
        fn from(e: atomicwrites::Error<Error>) -> Error {
            match e {
                atomicwrites::Error::Internal(x) => x.into(),
                atomicwrites::Error::User(x) => x,
            }
        }
    }

    pub trait ErrorExt: ::std::error::Error {
        unsafe fn fill_c_err(&self, err: *mut VdirsyncerError) {
            (*err).failed = true;
            (*err).msg = CString::new(self.description()).unwrap().into_raw();
        }
    }

    impl ErrorExt for Error {}

    #[repr(C)]
    pub struct VdirsyncerError {
        pub failed: bool,
        pub msg: *mut c_char,
    }
}

pub mod exports {
    use std::ffi::{CStr, CString};
    use std::ptr;
    use std::os::raw::c_char;
    use errors::*;

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_free_str(s: *const c_char) {
        CStr::from_ptr(s);
    }

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_clear_err(e: *mut VdirsyncerError) {
        CString::from_raw((*e).msg);
        (*e).msg = ptr::null_mut();
    }
}
