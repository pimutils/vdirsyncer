extern crate vobject;

use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use std::mem;
use std::ptr;

const EMPTY_STRING: *const c_char = b"\0" as *const u8 as *const c_char;

#[repr(C)]
pub struct VdirsyncerError {
    pub failed: bool,
    pub msg: *mut c_char,
}

// Workaround to be able to use opaque pointer
#[repr(C)]
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
pub unsafe extern "C" fn vdirsyncer_free_str(s: *const c_char) {
    CStr::from_ptr(s);
}

#[no_mangle]
pub unsafe extern "C" fn vdirsyncer_parse_component(s: *const c_char, err: *mut VdirsyncerError) -> *mut VdirsyncerComponent {
    let cstring = CStr::from_ptr(s);
    match vobject::parse_component(cstring.to_str().unwrap()) {
        Ok(x) => mem::transmute(Box::new(VdirsyncerComponent(x))),
        Err(e) => {
            (*err).failed = true;
            (*err).msg = CString::new(e.into_string()).unwrap().into_raw();
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
