use quick_xml;
use quick_xml::events::Event;

use errors::*;

use std::io::BufRead;

#[derive(Debug)]
pub struct Response {
    pub href: Option<String>,
    pub etag: Option<String>,
    pub mimetype: Option<String>,
    pub has_collection_tag: bool,
}

impl Response {
    pub fn new() -> Self {
        Response {
            href: None,
            etag: None,
            has_collection_tag: false,
            mimetype: None,
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

    fn next_response(&mut self) -> Fallible<Option<Response>> {
        let mut buf = vec![];

        #[derive(Debug, Clone, Copy)]
        enum State {
            Outer,
            Response,
            Href,
            ContentType,
            Etag,
        };

        let mut state = State::Outer;
        let mut current_response = Response::new();

        loop {
            match self
                .reader
                .read_namespaced_event(&mut buf, &mut self.ns_buf)?
            {
                (ns, Event::Start(ref e)) => {
                    match (state, ns, e.local_name()) {
                        (State::Outer, Some(b"DAV:"), b"response") => state = State::Response,
                        (State::Response, Some(b"DAV:"), b"href") => state = State::Href,
                        (State::Response, Some(b"DAV:"), b"getetag") => state = State::Etag,
                        (State::Response, Some(b"DAV:"), b"getcontenttype") => {
                            state = State::ContentType
                        }
                        (State::Response, Some(b"DAV:"), b"collection") => {
                            current_response.has_collection_tag = true;
                        }
                        _ => (),
                    }

                    debug!("State: {:?}", state);
                }
                (_, Event::Text(e)) => {
                    let txt = e.unescape_and_decode(&self.reader)?;
                    match state {
                        State::Href => current_response.href = Some(txt),
                        State::ContentType => current_response.mimetype = Some(txt),
                        State::Etag => current_response.etag = Some(txt),
                        _ => continue,
                    }
                    state = State::Response;
                }
                (ns, Event::End(e)) => match (state, ns, e.local_name()) {
                    (State::Response, Some(b"DAV:"), b"response") => {
                        return Ok(Some(current_response))
                    }
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
