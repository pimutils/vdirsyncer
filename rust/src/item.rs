use vobject;

use sha2::{Digest, Sha256};
use std::fmt::Write;

use errors::*;

#[derive(Clone)]
pub enum Item {
    Parsed(vobject::Component),
    Unparseable(String), // FIXME: maybe use https://crates.io/crates/terminated
}

impl Item {
    pub fn from_raw(raw: String) -> Self {
        match vobject::parse_component(&raw) {
            Ok(x) => Item::Parsed(x),
            // Don't chain vobject error here because it cannot be stored/cloned FIXME
            _ => Item::Unparseable(raw),
        }
    }

    pub fn from_component(component: vobject::Component) -> Self {
        Item::Parsed(component)
    }

    /// Global identifier of the item, across storages, doesn't change after a modification of the
    /// item.
    pub fn get_uid(&self) -> Option<String> {
        // FIXME: Cache
        if let Item::Parsed(ref c) = *self {
            let mut stack: Vec<&vobject::Component> = vec![c];

            while let Some(vobj) = stack.pop() {
                if let Some(prop) = vobj.get_only("UID") {
                    return Some(prop.value_as_string());
                }
                stack.extend(vobj.subcomponents.iter());
            }
        }
        None
    }

    pub fn with_uid(&self, uid: &str) -> Fallible<Self> {
        if let Item::Parsed(ref component) = *self {
            let mut new_component = component.clone();
            change_uid(&mut new_component, uid);
            Ok(Item::from_raw(vobject::write_component(&new_component)))
        } else {
            Err(Error::ItemUnparseable.into())
        }
    }

    /// Raw unvalidated content of the item
    pub fn get_raw(&self) -> String {
        match *self {
            Item::Parsed(ref component) => vobject::write_component(component),
            Item::Unparseable(ref x) => x.to_owned(),
        }
    }

    /// Component of item if parseable
    pub fn get_component(&self) -> Fallible<&vobject::Component> {
        match *self {
            Item::Parsed(ref component) => Ok(component),
            _ => Err(Error::ItemUnparseable.into()),
        }
    }

    /// Component of item if parseable
    pub fn into_component(self) -> Fallible<vobject::Component> {
        match self {
            Item::Parsed(component) => Ok(component),
            _ => Err(Error::ItemUnparseable.into()),
        }
    }

    /// Used for etags
    pub fn get_hash(&self) -> Fallible<String> {
        // FIXME: cache
        if let Item::Parsed(ref component) = *self {
            Ok(hash_component(component))
        } else {
            Err(Error::ItemUnparseable.into())
        }
    }

    /// Used for generating hrefs and matching up items during synchronization. This is either the
    /// UID or the hash of the item's content.
    pub fn get_ident(&self) -> Fallible<String> {
        if let Some(x) = self.get_uid() {
            return Ok(x);
        }
        // We hash the item instead of directly using its raw content, because
        // 1. The raw content might be really large, e.g. when it's a contact
        //    with a picture, which bloats the status file.
        //
        // 2. The status file would contain really sensitive information.
        self.get_hash()
    }

    pub fn is_parseable(&self) -> bool {
        if let Item::Parsed(_) = *self {
            true
        } else {
            false
        }
    }
}

fn change_uid(c: &mut vobject::Component, uid: &str) {
    let mut stack = vec![c];
    while let Some(component) = stack.pop() {
        match component.name.as_ref() {
            "VEVENT" | "VTODO" | "VJOURNAL" | "VCARD" => {
                if !uid.is_empty() {
                    component.set(vobject::Property::new("UID", uid));
                } else {
                    component.remove("UID");
                }
            }
            _ => (),
        }

        stack.extend(component.subcomponents.iter_mut());
    }
}

fn hash_component(c: &vobject::Component) -> String {
    let mut new_c = c.clone();
    {
        let mut stack = vec![&mut new_c];
        while let Some(component) = stack.pop() {
            // PRODID is changed by radicale for some reason after upload
            component.remove("PRODID");
            // Sometimes METHOD:PUBLISH is added by WebCAL providers, for us it doesn't make a difference
            component.remove("METHOD");
            // X-RADICALE-NAME is used by radicale, because hrefs don't really exist in their filesystem backend
            component.remove("X-RADICALE-NAME");
            // Those are from the VCARD specification and is supposed to change when the
            // item does -- however, we can determine that ourselves
            component.remove("REV");
            component.remove("LAST-MODIFIED");
            component.remove("CREATED");
            // Some iCalendar HTTP calendars generate the DTSTAMP at request time, so
            // this property always changes when the rest of the item didn't. Some do
            // the same with the UID.
            //
            // - Google's read-only calendar links
            // - http://www.feiertage-oesterreich.at/
            component.remove("DTSTAMP");
            component.remove("UID");

            if component.name == "VCALENDAR" {
                // CALSCALE's default value is gregorian
                let calscale = component.get_only("CALSCALE").map(|x| x.value_as_string());

                if let Some(x) = calscale {
                    if x == "GREGORIAN" {
                        component.remove("CALSCALE");
                    }
                }

                // Apparently this is set by Horde?
                // https://github.com/pimutils/vdirsyncer/issues/318
                // Also Google sets those properties
                component.remove("X-WR-CALNAME");
                component.remove("X-WR-TIMEZONE");

                component.subcomponents.retain(|c| c.name != "VTIMEZONE");
            }

            stack.extend(component.subcomponents.iter_mut());
        }
    }

    // FIXME: Possible optimization: Stream component to hasher instead of allocating new string
    let raw = vobject::write_component(&new_c);
    let mut lines: Vec<_> = raw.lines().collect();
    lines.sort();
    let mut hasher = Sha256::default();
    hasher.input(lines.join("\r\n").as_bytes());
    let digest = hasher.result();
    let mut rv = String::new();
    for &byte in digest.as_ref() {
        write!(&mut rv, "{:x}", byte).unwrap();
    }
    rv
}

pub mod exports {
    use super::Item;
    use errors::*;
    use std::ffi::{CStr, CString};
    use std::os::raw::c_char;
    use std::ptr;

    const EMPTY_STRING: *const c_char = b"\0" as *const u8 as *const c_char;

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_get_uid(c: *mut Item) -> *const c_char {
        match (*c).get_uid() {
            Some(x) => CString::new(x).unwrap().into_raw(),
            None => EMPTY_STRING,
        }
    }

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_get_raw(c: *mut Item) -> *const c_char {
        CString::new((*c).get_raw()).unwrap().into_raw()
    }

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_item_from_raw(s: *const c_char) -> *mut Item {
        let cstring = CStr::from_ptr(s);
        Box::into_raw(Box::new(Item::from_raw(
            cstring.to_str().unwrap().to_owned(),
        )))
    }

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_free_item(c: *mut Item) {
        let _: Box<Item> = Box::from_raw(c);
    }

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_with_uid(
        c: *mut Item,
        uid: *const c_char,
        err: *mut *mut ShippaiError,
    ) -> *mut Item {
        let uid_cstring = CStr::from_ptr(uid);
        if let Some(x) = export_result((*c).with_uid(uid_cstring.to_str().unwrap()), err) {
            Box::into_raw(Box::new(x))
        } else {
            ptr::null_mut()
        }
    }

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_get_hash(
        c: *mut Item,
        err: *mut *mut ShippaiError,
    ) -> *const c_char {
        if let Some(x) = export_result((*c).get_hash(), err) {
            CString::new(x).unwrap().into_raw()
        } else {
            ptr::null_mut()
        }
    }

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_item_is_parseable(c: *mut Item) -> bool {
        (*c).is_parseable()
    }
}
