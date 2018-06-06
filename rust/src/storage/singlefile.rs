use super::Storage;
use errors::*;
use std::collections::btree_map::Entry::*;
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{metadata, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::SystemTime;
use vobject;

use atomicwrites::{AllowOverwrite, AtomicFile};

use item::Item;

type ItemCache = BTreeMap<String, (Item, String)>;

pub struct SinglefileStorage {
    path: PathBuf,
    // href -> (item, etag)
    items_cache: Option<(ItemCache, SystemTime)>,
    buffered_mode: bool,
    dirty_cache: bool,
}

impl SinglefileStorage {
    pub fn new<P: AsRef<Path>>(path: P) -> Self {
        SinglefileStorage {
            path: path.as_ref().to_owned(),
            items_cache: None,
            buffered_mode: false,
            dirty_cache: false,
        }
    }

    fn get_items(&mut self) -> Fallible<&mut ItemCache> {
        if self.items_cache.is_none() {
            self.list()?;
        }
        Ok(&mut self.items_cache.as_mut().unwrap().0)
    }

    fn write_back(&mut self) -> Fallible<()> {
        self.dirty_cache = true;
        if self.buffered_mode {
            return Ok(());
        }

        self.flush()?;
        Ok(())
    }
}

pub mod exports {
    use super::*;
    use std::ffi::CStr;
    use std::os::raw::c_char;

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_init_singlefile(path: *const c_char) -> *mut Box<Storage> {
        let cstring = CStr::from_ptr(path);
        Box::into_raw(Box::new(Box::new(SinglefileStorage::new(
            cstring.to_str().unwrap(),
        ))))
    }
}

impl Storage for SinglefileStorage {
    fn list<'a>(&'a mut self) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        let mut new_cache = BTreeMap::new();
        let mtime = metadata(&self.path)?.modified()?;
        let mut f = File::open(&self.path)?;
        let mut s = String::new();
        f.read_to_string(&mut s)?;
        for component in split_collection(&s)? {
            let item = Item::from_component(component);
            let hash = item.get_hash()?;
            let ident = item.get_ident()?;
            new_cache.insert(ident, (item, hash));
        }

        self.items_cache = Some((new_cache, mtime));
        self.dirty_cache = false;
        Ok(Box::new(self.items_cache.as_ref().unwrap().0.iter().map(
            |(href, &(_, ref etag))| (href.clone(), etag.clone()),
        )))
    }

    fn get(&mut self, href: &str) -> Fallible<(Item, String)> {
        match self.get_items()?.get(href) {
            Some(&(ref href, ref etag)) => Ok((href.clone(), etag.clone())),
            None => Err(Error::ItemNotFound {
                href: href.to_owned(),
            })?,
        }
    }

    fn upload(&mut self, item: Item) -> Fallible<(String, String)> {
        let hash = item.get_hash()?;
        let href = item.get_ident()?;
        match self.get_items()?.entry(href.clone()) {
            Occupied(_) => Err(Error::ItemAlreadyExisting { href: href.clone() })?,
            Vacant(vc) => vc.insert((item, hash.clone())),
        };
        self.write_back()?;
        Ok((href, hash))
    }

    fn update(&mut self, href: &str, item: Item, etag: &str) -> Fallible<String> {
        let hash = match self.get_items()?.entry(href.to_owned()) {
            Occupied(mut oc) => {
                if oc.get().1 == etag {
                    let hash = item.get_hash()?;
                    oc.insert((item, hash.clone()));
                    hash
                } else {
                    Err(Error::WrongEtag {
                        href: href.to_owned(),
                    })?
                }
            }
            Vacant(_) => Err(Error::ItemNotFound {
                href: href.to_owned(),
            })?,
        };
        self.write_back()?;
        Ok(hash)
    }

    fn delete(&mut self, href: &str, etag: &str) -> Fallible<()> {
        match self.get_items()?.entry(href.to_owned()) {
            Occupied(oc) => {
                if oc.get().1 == etag {
                    oc.remove();
                } else {
                    Err(Error::WrongEtag {
                        href: href.to_owned(),
                    })?
                }
            }
            Vacant(_) => Err(Error::ItemNotFound {
                href: href.to_owned(),
            })?,
        }
        self.write_back()?;
        Ok(())
    }

    fn buffered(&mut self) {
        self.buffered_mode = true;
    }

    fn flush(&mut self) -> Fallible<()> {
        if !self.dirty_cache {
            return Ok(());
        }
        let (items, mtime) = self.items_cache.take().unwrap();

        let af = AtomicFile::new(&self.path, AllowOverwrite);
        let content = join_collection(items.into_iter().map(|(_, (item, _))| item))?;

        let path = &self.path;
        let write_inner = |f: &mut File| -> Fallible<()> {
            f.write_all(content.as_bytes())?;
            let real_mtime = metadata(path)?.modified()?;
            if mtime != real_mtime {
                Err(Error::MtimeMismatch {
                    filepath: path.to_string_lossy().into_owned(),
                })?;
            }
            Ok(())
        };

        af.write::<(), ::failure::Compat<::failure::Error>, _>(|f| {
            write_inner(f).map_err(|e| e.compat())
        })?;

        self.dirty_cache = false;

        Ok(())
    }
}

pub fn split_collection(mut input: &str) -> Fallible<Vec<vobject::Component>> {
    let mut rv = vec![];
    while !input.is_empty() {
        let (component, remainder) =
            vobject::read_component(input).map_err(::failure::SyncFailure::new)?;
        input = remainder;

        match component.name.as_ref() {
            "VCALENDAR" => rv.extend(split_vcalendar(component)?),
            "VCARD" => rv.push(component),
            "VADDRESSBOOK" => for vcard in component.subcomponents {
                if vcard.name != "VCARD" {
                    Err(Error::UnexpectedVobject {
                        found: vcard.name.clone(),
                        expected: "VCARD".to_owned(),
                    })?;
                }
                rv.push(vcard);
            },
            _ => Err(Error::UnexpectedVobject {
                found: component.name.clone(),
                expected: "VCALENDAR | VCARD | VADDRESSBOOK".to_owned(),
            })?,
        }
    }

    Ok(rv)
}

/// Split one VCALENDAR component into multiple VCALENDAR components
#[inline]
fn split_vcalendar(mut vcalendar: vobject::Component) -> Fallible<Vec<vobject::Component>> {
    vcalendar.props.remove("METHOD");

    let mut timezones = BTreeMap::new(); // tzid => component
    let mut subcomponents = vec![];

    for component in vcalendar.subcomponents.drain(..) {
        match component.name.as_ref() {
            "VTIMEZONE" => {
                let tzid = match component.get_only("TZID") {
                    Some(x) => x.value_as_string().clone(),
                    None => continue,
                };
                timezones.insert(tzid, component);
            }
            "VTODO" | "VEVENT" | "VJOURNAL" => subcomponents.push(component),
            _ => Err(Error::UnexpectedVobject {
                found: component.name.clone(),
                expected: "VTIMEZONE | VTODO | VEVENT | VJOURNAL".to_owned(),
            })?,
        };
    }

    let mut by_uid = BTreeMap::new();
    let mut no_uid = vec![];

    for component in subcomponents {
        let uid = component.get_only("UID").cloned();

        let mut wrapper = match uid
            .as_ref()
            .and_then(|u| by_uid.remove(&u.value_as_string()))
        {
            Some(x) => x,
            None => vcalendar.clone(),
        };

        let mut required_tzids = BTreeSet::new();
        for props in component.props.values() {
            for prop in props {
                if let Some(x) = prop.params.get("TZID") {
                    required_tzids.insert(x.to_owned());
                }
            }
        }

        for tzid in required_tzids {
            if let Some(tz) = timezones.get(&tzid) {
                wrapper.subcomponents.push(tz.clone());
            }
        }

        wrapper.subcomponents.push(component);

        match uid {
            Some(p) => {
                by_uid.insert(p.value_as_string(), wrapper);
            }
            None => no_uid.push(wrapper),
        }
    }

    Ok(by_uid
        .into_iter()
        .map(|(_, v)| v)
        .chain(no_uid.into_iter())
        .collect())
}

fn join_collection<I: Iterator<Item = Item>>(item_iter: I) -> Fallible<String> {
    let mut items = item_iter.peekable();

    let item_name = match items.peek() {
        Some(x) => x.get_component()?.name.clone(),
        None => return Ok("".to_owned()),
    };

    let wrapper_name = match item_name.as_ref() {
        "VCARD" => "VADDRESSBOOK",
        "VCALENDAR" => "VCALENDAR",
        _ => Err(Error::UnexpectedVobject {
            found: item_name.clone(),
            expected: "VCARD | VCALENDAR".to_owned(),
        })?,
    };

    let mut wrapper = vobject::Component::new(wrapper_name);
    let mut version: Option<vobject::Property> = None;

    for item in items {
        let mut c = item.into_component()?;
        if c.name != item_name {
            return Err(Error::UnexpectedVobject {
                found: c.name,
                expected: item_name.clone(),
            }.into());
        }

        if item_name == wrapper_name {
            wrapper.subcomponents.extend(c.subcomponents.drain(..));
            match (version.as_ref(), c.get_only("VERSION")) {
                (Some(x), Some(y)) if x.raw_value != y.raw_value => {
                    return Err(Error::UnexpectedVobjectVersion {
                        expected: x.raw_value.clone(),
                        found: y.raw_value.clone(),
                    }.into());
                }
                (None, Some(_)) => (),
                _ => continue,
            }
            version = c.get_only("VERSION").cloned();
        } else {
            wrapper.subcomponents.push(c);
        }
    }

    if let Some(v) = version {
        wrapper.set(v);
    }

    Ok(vobject::write_component(&wrapper))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn check_roundtrip(raw: &str) {
        let components = split_collection(raw).unwrap();
        let raw2 = join_collection(components.into_iter().map(Item::from_component)).unwrap();
        assert_eq!(
            Item::from_raw(raw.to_owned()).get_hash().unwrap(),
            Item::from_raw(raw2.to_owned()).get_hash().unwrap()
        );
    }

    #[test]
    fn test_wrapper_properties_roundtrip() {
        let raw = r#"BEGIN:VCALENDAR
PRODID:-//Google Inc//Google Calendar 70.9054//EN
X-WR-CALNAME:markus.unterwaditzer@runtastic.com
X-WR-TIMEZONE:Europe/Vienna
VERSION:2.0
CALSCALE:GREGORIAN
BEGIN:VEVENT
DTSTART;TZID=Europe/Vienna:20171012T153000
DTEND;TZID=Europe/Vienna:20171012T170000
DTSTAMP:20171009T085029Z
UID:test@test.com
STATUS:CONFIRMED
SUMMARY:Test
TRANSP:OPAQUE
END:VEVENT
END:VCALENDAR"#;
        check_roundtrip(raw);
    }
}
