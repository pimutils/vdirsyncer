use failure;

pub type Fallible<T> = Result<T, failure::Error>;

#[derive(Debug, Fail)]
#[fail(display = "The item cannot be parsed")]
pub struct ItemUnparseable;

#[derive(Debug, Fail)]
#[fail(display = "Unexpected version {}, expected {}", found, expected)]
pub struct UnexpectedVobjectVersion {
    pub found: String,
    pub expected: String,
}

#[derive(Debug, Fail)]
#[fail(display = "Unexpected component {}, expected {}", found, expected)]
pub struct UnexpectedVobject {
    pub found: String,
    pub expected: String,
}

#[derive(Debug, Fail)]
#[fail(display = "Item '{}' not found", href)]
pub struct ItemNotFound {
    pub href: String,
}

#[derive(Debug, Fail)]
#[fail(display = "The href '{}' is already taken", href)]
pub struct ItemAlreadyExisting {
    pub href: String,
}

#[derive(Debug, Fail)]
#[fail(display = "A wrong etag for '{}' was provided. Another client's requests might \
                  conflict with vdirsyncer.",
       href)]
pub struct WrongEtag {
    pub href: String,
}

#[derive(Debug, Fail)]
#[fail(display = "The mtime for '{}' has unexpectedly changed. Please close other programs\
                  accessing this file.",
       filepath)]
pub struct MtimeMismatch {
    pub filepath: String,
}

#[derive(Debug, Fail)]
#[fail(display = "Tried to write to a read-only storage.")]
pub struct ReadOnly;

pub unsafe fn export_result<V>(
    res: Result<V, failure::Error>,
    c_err: *mut *mut exports::ShippaiError,
) -> Option<V> {
    match res {
        Ok(v) => Some(v),
        Err(e) => {
            *c_err = Box::into_raw(Box::new(e.into()));
            None
        }
    }
}

pub mod exports {
    shippai_export! {
        super::ItemUnparseable as ITEM_UNPARSEABLE,
        super::UnexpectedVobjectVersion as UNEXPECTED_VOBJECT_VERSION,
        super::UnexpectedVobject as UNEXPECTED_VOBJECT,
        super::ItemNotFound as ITEM_NOT_FOUND,
        super::ItemAlreadyExisting as ITEM_ALREADY_EXISTING,
        super::WrongEtag as WRONG_ETAG,
        super::MtimeMismatch as MTIME_MISMATCH,
        super::ReadOnly as READ_ONLY
    }
}
