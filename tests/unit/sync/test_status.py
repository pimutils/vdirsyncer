import pytest

from hypothesis import assume, given
import hypothesis.strategies as st

from vdirsyncer.sync.status import SqliteStatus


@pytest.fixture(params=[
    SqliteStatus
])
def new_status(request):
    return request.param


@given(status_dict=st.dictionaries(
    st.text(),
    st.tuples(*(
        st.fixed_dictionaries({
            'href': st.text(),
            'hash': st.text(),
            'etag': st.text()
        }) for _ in range(2)
    ))
))
def test_legacy_status(new_status, status_dict):
    hrefs_a = {meta_a['href'] for meta_a, meta_b in status_dict.values()}
    hrefs_b = {meta_b['href'] for meta_a, meta_b in status_dict.values()}
    assume(len(hrefs_a) == len(status_dict))
    assume(len(hrefs_b) == len(status_dict))

    status = new_status()
    status.load_legacy_status(status_dict)
    assert dict(status.to_legacy_status()) == status_dict
