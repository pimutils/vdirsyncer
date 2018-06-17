use quick_xml;
use quick_xml::events::Event;

use errors::*;

use std::io::BufRead;

#[derive(Debug)]
pub struct Response {
    pub href: Option<String>,
    pub etag: Option<String>,
    pub mimetype: Option<String>,
    pub current_user_principal: Option<String>,
    pub calendar_home_set: Option<String>,
    pub addressbook_home_set: Option<String>,
    pub is_collection: bool,
    pub is_calendar: bool,
    pub is_addressbook: bool,
}

impl Response {
    pub fn new() -> Self {
        Response {
            href: None,
            etag: None,
            mimetype: None,
            current_user_principal: None,
            calendar_home_set: None,
            addressbook_home_set: None,
            is_collection: false,
            is_calendar: false,
            is_addressbook: false,
        }
    }
}

pub struct ListingParser<T: BufRead> {
    reader: quick_xml::Reader<T>,
    ns_buf: Vec<u8>,
}

impl<T: BufRead> ListingParser<T> {
    pub fn new(mut reader: quick_xml::Reader<T>) -> Self {
        reader.expand_empty_elements(true);
        reader.trim_text(true);
        reader.check_end_names(true);
        reader.check_comments(false);

        ListingParser {
            reader,
            ns_buf: vec![],
        }
    }

    pub fn next_response(&mut self) -> Fallible<Option<Response>> {
        let mut buf = vec![];

        #[derive(Debug, Clone, Copy)]
        enum State {
            Outer,
            Response,
            Href,
            ContentType,
            Etag,
            CurrentUserPrincipal,
            CalendarHomeSet,
            AddressbookHomeSet,
            ResourceType,
        };

        let mut state = State::Outer;
        let mut current_response = Response::new();

        loop {
            match self
                .reader
                .read_namespaced_event(&mut buf, &mut self.ns_buf)?
            {
                (ns, Event::Start(ref e)) => {
                    let old_state = state;
                    match (state, ns, e.local_name()) {
                        // Item listings
                        (State::Outer, Some(b"DAV:"), b"response") => state = State::Response,
                        (State::Response, Some(b"DAV:"), b"href") => state = State::Href,
                        (State::Response, Some(b"DAV:"), b"getetag") => state = State::Etag,
                        (State::Response, Some(b"DAV:"), b"getcontenttype") => {
                            state = State::ContentType
                        }
                        // Collection discovery
                        (State::Response, Some(b"DAV:"), b"current-user-principal") => {
                            state = State::CurrentUserPrincipal
                        }
                        (
                            State::Response,
                            Some(b"urn:ietf:params:xml:ns:caldav"),
                            b"calendar-home-set",
                        ) => state = State::CalendarHomeSet,
                        (
                            State::Response,
                            Some(b"urn:ietf:params:xml:ns:carddav"),
                            b"addressbook-home-set",
                        ) => state = State::AddressbookHomeSet,
                        (State::Response, Some(b"DAV:"), b"resourcetype") => {
                            state = State::ResourceType
                        }
                        (State::ResourceType, Some(b"DAV:"), b"collection") => {
                            current_response.is_collection = true;
                            state = State::Response;
                        }
                        (
                            State::ResourceType,
                            Some(b"urn:ietf:params:xml:ns:caldav"),
                            b"calendar",
                        ) => {
                            current_response.is_calendar = true;
                            state = State::Response;
                        }
                        (
                            State::ResourceType,
                            Some(b"urn:ietf:params:xml:ns:carddav"),
                            b"addressbook",
                        ) => {
                            current_response.is_addressbook = true;
                            state = State::Response;
                        }
                        _ => (),
                    }

                    debug!("State: {:?} => {:?}", old_state, state);
                }
                (_, Event::Text(e)) => {
                    let txt = e.unescape_and_decode(&self.reader)?;
                    match state {
                        // Item listings
                        State::Href => current_response.href = Some(txt),
                        State::ContentType => current_response.mimetype = Some(txt),
                        State::Etag => current_response.etag = Some(txt),

                        // Collection discovery
                        State::CurrentUserPrincipal => {
                            current_response.current_user_principal = Some(txt)
                        }
                        State::CalendarHomeSet => current_response.calendar_home_set = Some(txt),
                        State::AddressbookHomeSet => {
                            current_response.addressbook_home_set = Some(txt)
                        }
                        _ => continue,
                    }
                    state = State::Response;
                }
                (ns, Event::End(e)) => match (state, ns, e.local_name()) {
                    (State::Response, Some(b"DAV:"), b"response") => {
                        return Ok(Some(current_response))
                    }
                    (State::Href, Some(b"DAV:"), b"href")
                    | (_, Some(b"DAV:"), b"getetag")
                    | (_, Some(b"DAV:"), b"getcontenttype")
                    | (_, Some(b"DAV:"), b"current-user-principal")
                    | (_, Some(b"urn:ietf:params:xml:ns:caldav"), b"calendar-home-set")
                    | (_, Some(b"urn:ietf:params:xml:ns:carddav"), b"addressbook-home-set")
                    | (_, Some(b"DAV:"), b"resourcetype") => state = State::Response,
                    _ => (),
                },
                (_, Event::Eof) => return Ok(None),
                _ => (),
            }
        }
    }

    pub fn get_all_responses(&mut self) -> Fallible<Vec<Response>> {
        let mut rv = vec![];
        while let Some(x) = self.next_response()? {
            rv.push(x);
        }
        Ok(rv)
    }
}
