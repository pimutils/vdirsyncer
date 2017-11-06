use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use std::mem;
use std::ptr;

use vobject;
use ring;

use std::fmt::Write;
use VdirsyncerError;


const EMPTY_STRING: *const c_char = b"\0" as *const u8 as *const c_char;

pub struct VdirsyncerComponent(vobject::Component);

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_get_uid(c: *mut VdirsyncerComponent) -> *const c_char {
    match safe_get_uid(&(*c).0) {
        Some(x) => CString::new(x).unwrap().into_raw(),
        None => EMPTY_STRING
    }
}

#[inline]
fn safe_get_uid(c: &vobject::Component) -> Option<String> {
    let mut stack = vec![c];

    while let Some(vobj) = stack.pop() {
        if let Some(prop) = vobj.get_only("UID") {
            return Some(prop.value_as_string());
        }
        stack.extend(vobj.subcomponents.iter());
    };
    None
}


#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_parse_component(s: *const c_char, err: *mut VdirsyncerError) -> *mut VdirsyncerComponent {
    let cstring = CStr::from_ptr(s);
    match vobject::parse_component(cstring.to_str().unwrap()) {
        Ok(x) => mem::transmute(Box::new(VdirsyncerComponent(x))),
        Err(e) => {
            (*err).failed = true;
            (*err).msg = CString::new(e.description()).unwrap().into_raw();
            mem::zeroed()
        }
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_free_component(c: *mut VdirsyncerComponent) {
    let _: Box<VdirsyncerComponent> = mem::transmute(c);
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_clear_err(e: *mut VdirsyncerError) {
    CString::from_raw((*e).msg);
    (*e).msg = ptr::null_mut();
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_change_uid(c: *mut VdirsyncerComponent, uid: *const c_char) {
    let uid_cstring = CStr::from_ptr(uid);
    change_uid(&mut (*c).0, uid_cstring.to_str().unwrap());
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
            },
            _ => ()
        }

        stack.extend(component.subcomponents.iter_mut());
    }
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_clone_component(c: *mut VdirsyncerComponent) -> *mut VdirsyncerComponent {
    mem::transmute(Box::new((*c).0.clone()))
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_write_component(c: *mut VdirsyncerComponent) -> *const c_char {
    CString::new(vobject::write_component(&(*c).0)).unwrap().into_raw()
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_hash_component(c: *mut VdirsyncerComponent) -> *const c_char {
    CString::new(safe_hash_component(&(*c).0)).unwrap().into_raw()
}

fn safe_hash_component(c: &vobject::Component) -> String {
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
            // Apparently this is set by Horde?
            // https://github.com/pimutils/vdirsyncer/issues/318
            component.remove("X-WR-CALNAME");
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
                component.subcomponents.retain(|ref c| c.name != "VTIMEZONE");
            }

            stack.extend(component.subcomponents.iter_mut());
        }
    }

    // FIXME: Possible optimization: Stream component to hasher instead of allocating new string
    let digest = ring::digest::digest(&ring::digest::SHA256, vobject::write_component(&new_c).as_bytes());
    let mut rv = String::new();
    for &byte in digest.as_ref() {
        write!(&mut rv, "{:x}", byte).unwrap();
    }
    rv
}
