use failure;

pub type Fallible<T> = Result<T, failure::Error>;

shippai_export!();

#[derive(Debug, Fail, Shippai)]
#[fail(display = "The item cannot be parsed")]
pub struct ItemUnparseable;

#[derive(Debug, Fail, Shippai)]
#[fail(display = "Unexpected version {}, expected {}", found, expected)]
pub struct UnexpectedVobjectVersion {
    pub found: String,
    pub expected: String,
}

#[derive(Debug, Fail, Shippai)]
#[fail(display = "Unexpected component {}, expected {}", found, expected)]
pub struct UnexpectedVobject {
    pub found: String,
    pub expected: String,
}

#[derive(Debug, Fail, Shippai)]
#[fail(display = "Item '{}' not found", href)]
pub struct ItemNotFound {
    pub href: String,
}

#[derive(Debug, Fail, Shippai)]
#[fail(display = "The href '{}' is already taken", href)]
pub struct ItemAlreadyExisting {
    pub href: String,
}

#[derive(Debug, Fail, Shippai)]
#[fail(display = "A wrong etag for '{}' was provided. Another client's requests might \
                  conflict with vdirsyncer.",
       href)]
pub struct WrongEtag {
    pub href: String,
}

#[derive(Debug, Fail, Shippai)]
#[fail(display = "The mtime for '{}' has unexpectedly changed. Please close other programs\
                  accessing this file.",
       filepath)]
pub struct MtimeMismatch {
    pub filepath: String,
}

pub unsafe fn export_result<V>(
    res: Result<V, failure::Error>,
    c_err: *mut *mut ShippaiError,
) -> Option<V> {
    match res {
        Ok(v) => Some(v),
        Err(e) => {
            *c_err = Box::into_raw(Box::new(e.into()));
            None
        }
    }
}
