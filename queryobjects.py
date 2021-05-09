from typing import List, Tuple

from mwparserfromhell.wikicode import Wikicode

from pyetymology.eobjects.wikikey import WikiKey
from pyetymology.etyobjects import Originator
from pyetymology.langhelper import Language
from pyetymology.emulate.moduleimpl import QueryFlags
from pyetymology.emulate import moduleimpl

from pyetymology.queryutils import query_to_qparts


class ThickQuery():
    def __init__(self,
                 me: str, word: str, langname: str, def_id: str,
                 res: Wikicode, wikitext: str, dom: List[Wikicode],
                 origin: Originator, qflags: QueryFlags = None):
        self.me = me
        # self.word = word
        # self.lang = langname

        _word, _Lang, _qflags = query_to_qparts(me)
        # _def_id = _qflags.def_id
        self.queryflags = _qflags
        assert def_id == _qflags.def_id
        self.def_id = _qflags.def_id

        self.word = _word

        self.langname = _Lang.langname
        assert word == self.word
        assert langname == self.langname
        # assert def_id == qdef_id
        self.Lang = _Lang
        assert self.Lang  # It must not be blank.

        self.res = res
        self.wikitext = wikitext
        self.dom = dom

        self.origin = origin




    def biglang(self):
        return self.Lang
    def to_tupled(self):
        return (self.me, self.word, self.langname, self.def_id), (self.res, self.wikitext, self.dom), self.origin
    @property
    def query(self):
        return (self.me, self.word, self.langname, self.def_id)
    @property
    def word_urlify(self):
        # return moduleimpl.urlword(self.word, self.lang)
         return moduleimpl.urlword(self.word, self.biglang(), crash=True) # we should actually crash because queries *must* have a language defined
    @property
    def wikitext_link(self):
        return moduleimpl.to_link(self.word, self.biglang())

    @classmethod
    def from_key(cls, wkey: WikiKey, me:str, origin):
        return ThickQuery(me=me, word=wkey.word, langname=wkey.Lang.langname, def_id=wkey.def_id, res=wkey.result.wikiresponse, wikitext=wkey.result.wikitext, dom=wkey.result.dom, origin=origin)
        pass

class DummyQuery(ThickQuery):
    def __init__(self, me:str, origin:Originator, child_queries: List[str], with_lang:Language):
        word, _Lang, _qflags = query_to_qparts(me)
        biglang = with_lang

        me2 = word + "#" + biglang.langqstr
        lang = biglang.langname
        def_id = _qflags.def_id
        super().__init__(me=me2, word=word, langname=lang, def_id=def_id, res=None, wikitext=None, dom=None, origin=origin, qflags=_qflags)
        self.child_queries = child_queries

def from_tupled(query: Tuple[str, str, str, str], wikiresponse: Tuple[Wikicode, str, List[Wikicode]], origin: Originator):
    return ThickQuery(*query, *wikiresponse, origin)

