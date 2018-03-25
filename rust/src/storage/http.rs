use std::collections::BTreeMap;

use reqwest;

use super::Storage;
use errors::*;
use super::singlefile::split_collection;

use item::Item;

type ItemCache = BTreeMap<String, (Item, String)>;
type Username = String;
type Password = String;
type Auth = (Username, Password);

pub struct HttpStorage {
    url: String,
    auth: Option<Auth>,
    // href -> (item, etag)
    items_cache: Option<ItemCache>,
}

impl HttpStorage {
    pub fn new(url: String, auth: Option<Auth>) -> Self {
        HttpStorage {
            url: url,
            auth: auth,
            items_cache: None,
        }
    }

    fn get_items(&mut self) -> Fallible<&mut ItemCache> {
        if self.items_cache.is_none() {
            self.list()?;
        }
        Ok(self.items_cache.as_mut().unwrap())
    }
}

impl Storage for HttpStorage {
    fn list<'a>(&'a mut self) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        let mut new_cache = BTreeMap::new();
        let client = reqwest::Client::new();
        let mut request_builder = client.get(&self.url);

        if let Some((ref username, ref password)) = self.auth {
            request_builder.basic_auth(&username[..], Some(&password[..]));
        }
        let mut response = request_builder.send()?.error_for_status()?;
        let s = response.text()?;
        for component in split_collection(&s)? {
            let mut item = Item::from_component(component);
            item = item.with_uid(&item.get_hash()?)?;
            let ident = item.get_ident()?;
            let hash = item.get_hash()?;
            new_cache.insert(ident, (item, hash));
        }

        self.items_cache = Some(new_cache);
        Ok(Box::new(self.items_cache.as_ref().unwrap().iter().map(
            |(href, &(_, ref etag))| (href.clone(), etag.clone()),
        )))
    }

    fn get(&mut self, href: &str) -> Fallible<(Item, String)> {
        match self.get_items()?.get(href) {
            Some(&(ref href, ref etag)) => Ok((href.clone(), etag.clone())),
            None => Err(ItemNotFound {
                href: href.to_owned(),
            })?,
        }
    }

    fn upload(&mut self, _item: Item) -> Fallible<(String, String)> {
        Err(ReadOnly)?
    }

    fn update(&mut self, _href: &str, _item: Item, _etag: &str) -> Fallible<String> {
        Err(ReadOnly)?
    }

    fn delete(&mut self, _href: &str, _etag: &str) -> Fallible<()> {
        Err(ReadOnly)?
    }
}

pub mod exports {
    use super::*;
    use std::ffi::CStr;
    use std::os::raw::c_char;

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_init_http(
        url: *const c_char,
        username: *const c_char,
        password: *const c_char
    ) -> *mut Box<Storage> {
        let url_cstring = CStr::from_ptr(url);
        let username_cstring = CStr::from_ptr(username);
        let password_cstring = CStr::from_ptr(password);
        let username_dec = username_cstring.to_str().unwrap();
        let password_dec = password_cstring.to_str().unwrap();
        
        let auth = if !username_dec.is_empty() && !password_dec.is_empty() {
            Some((username_dec.to_owned(), password_dec.to_owned()))
        } else {
            None
        };

        Box::into_raw(Box::new(Box::new(HttpStorage::new(
            url_cstring.to_str().unwrap().to_owned(),
            auth
        ))))
    }
}
