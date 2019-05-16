use super::{ConfigurableStorage, Storage, StorageConfig};
use errors::*;
use glob::glob;
use std::collections::btree_map::Entry::*;
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{metadata, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::SystemTime;
use vobject;

use atomicwrites::{AllowOverwrite, AtomicFile};

use item::Item;

#[derive(Clone)]
struct HashableItem(Item);

impl HashableItem {
    /// Create a wrapper around `item` that guarantees the `get_hash()` method will return `Ok`.
    pub fn new(item: Item) -> Fallible<Self> {
        item.get_hash()?;
        Ok(HashableItem(item))
    }

    #[inline]
    pub fn get_etag(&self) -> &str {
        self.0.get_hash().unwrap()
    }
}

impl Into<Item> for HashableItem {
    fn into(self) -> Item {
        self.0
    }
}

// href -> item
// etag = item.get_hash()
type ItemCache = BTreeMap<String, HashableItem>;

pub struct SinglefileStorage {
    path: PathBuf,
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
            let ident = item.get_ident()?.to_owned();
            new_cache.insert(ident, HashableItem::new(item)?);
        }

        self.items_cache = Some((new_cache, mtime));
        self.dirty_cache = false;
        Ok(Box::new(self.items_cache.as_ref().unwrap().0.iter().map(
            |(href, item)| (href.clone(), item.get_etag().to_owned()),
        )))
    }

    fn get(&mut self, href: &str) -> Fallible<(Item, String)> {
        match self.get_items()?.get(href) {
            Some(entry) => Ok((entry.clone().into(), entry.get_etag().to_owned())),
            None => Err(Error::ItemNotFound {
                href: href.to_owned(),
            })?,
        }
    }

    fn upload(&mut self, item: Item) -> Fallible<(String, String)> {
        let hash = item.get_hash()?.to_owned();
        let href = item.get_ident()?.to_owned();
        match self.get_items()?.entry(href.clone()) {
            Occupied(_) => Err(Error::ItemAlreadyExisting { href: href.clone() })?,
            Vacant(vc) => vc.insert(HashableItem::new(item)?),
        };
        self.write_back()?;
        Ok((href, hash))
    }

    fn update(&mut self, href: &str, item: Item, etag: &str) -> Fallible<String> {
        let hash = match self.get_items()?.entry(href.to_owned()) {
            Occupied(mut oc) => {
                if oc.get().get_etag() == etag {
                    let hash = item.get_hash()?.to_owned();
                    oc.insert(HashableItem::new(item)?);
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
                if oc.get().get_etag() == etag {
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
        let content = join_collection(items.into_iter().map(|(_, item)| item.into()))?;

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

#[derive(Clone, Serialize, Deserialize)]
pub struct Config {
    path: String,
    collection: Option<String>,
}

impl StorageConfig for Config {
    fn get_collection(&self) -> Option<&str> {
        self.collection.as_ref().map(|x| &**x)
    }
}

impl ConfigurableStorage for SinglefileStorage {
    type Config = Config;

    fn from_config(config: Self::Config) -> Fallible<Self> {
        Ok(SinglefileStorage::new(config.path))
    }

    fn discover(config: Self::Config) -> Fallible<Box<Iterator<Item = Self::Config>>> {
        let basepath = config.path;

        if config.collection.is_some() {
            Err(Error::BadDiscoveryConfig {
                msg: "collection argument must not be given when discovering collections/storages"
                    .to_owned(),
            })?;
        }

        if basepath.contains('*') {
            Err(Error::BadDiscoveryConfig {
                msg: "Wildcards are not allowed. Use '%s' exactly once as placeholder for the collection name.".to_owned()
            })?;
        }

        let placeholder_start = {
            let mut placeholders = basepath.match_indices("%s");
            if let Some((i, _)) = placeholders.next() {
                if placeholders.next().is_some() {
                    Err(Error::BadDiscoveryConfig {
                        msg: "Too many occurences of '%s'. May occur only once!".to_owned(),
                    })?;
                }

                i
            } else {
                Err(Error::BadDiscoveryConfig {
                    msg: "Put '%s' into your 'path' as a wildcard.".to_owned(),
                })?
            }
        };

        Ok(Box::new(glob(&basepath.replace("%s", "*"))?.filter_map(
            move |entry| {
                let path = entry.ok()?;
                let path_str = path.to_str()?;
                let collection_end = placeholder_start + 2 + path_str.len() - basepath.len();
                Some(Config {
                    path: path_str.to_owned(),
                    collection: Some(path_str[placeholder_start..collection_end].to_owned()),
                })
            },
        )))
    }

    fn create(_config: Self::Config) -> Fallible<Self::Config> {
        unimplemented!();
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
            "VADDRESSBOOK" => {
                for vcard in component.subcomponents {
                    if vcard.name != "VCARD" {
                        Err(Error::UnexpectedVobject {
                            found: vcard.name.clone(),
                            expected: "VCARD".to_owned(),
                        })?;
                    }
                    rv.push(vcard);
                }
            }
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
            }
            .into());
        }

        if item_name == wrapper_name {
            wrapper.subcomponents.extend(c.subcomponents.drain(..));
            match (version.as_ref(), c.get_only("VERSION")) {
                (Some(x), Some(y)) if x.raw_value != y.raw_value => {
                    return Err(Error::UnexpectedVobjectVersion {
                        expected: x.raw_value.clone(),
                        found: y.raw_value.clone(),
                    }
                    .into());
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
