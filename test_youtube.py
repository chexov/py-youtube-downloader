#!/usr/bin/env python
# encoding: utf-8

import youtube as y
def test_getPageToken():
    token = y.Youtube("QkzCi5mHvkc").pageToken()
    assert isinstance(token, basestring)
    assert len(token) > 0, "Token was zero length"

if __name__ == '__main__':
    import nose
    nose.main()