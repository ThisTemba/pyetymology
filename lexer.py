from typing import List, Union

from mwparserfromhell.wikicode import Wikicode

import pyetymology.wikt_api as wikt
from pyetymology.langcode import poscodes


def get_header_type(wc: Wikicode, lvl: int):
    breve: str = wc[lvl:]  # len("===") == 3 # "===Pronunciation===" --> "Pronunciation==="
    header_type = breve[:breve.index("=" * lvl)]  # "Pronunciation===" -> "Pronunciation"
    return header_type


class Header:

    def __init__(self, wikicode: Wikicode, subordinates: List[Wikicode], header_type: str = None, idx: int = None,
                 metainfo=None, lvl: int = 3):
        assert wikicode.startswith("="*lvl) and not wikicode.startswith("="*(lvl+1))  # assert that the level is correct
        if header_type is None:  # auto header type deduce
            breve: str = wikicode[lvl:]  # len("===") == 3 # "===Pronunciation===" --> "Pronunciation==="
            header_type = breve[:breve.index("="*lvl)]  # "Pronunciation===" -> "Pronunciation"

            if idx is None and header_type.startswith("Etymology "):  # auto idx deduce
                assert len(header_type) >= 11  # len("Etymology 1")
                idx = int(header_type[10:])
                assert idx and type(idx) == int
                header_type = "Etymology"
            defn_flag = header_type in poscodes.all
            if defn_flag and metainfo is None:
                metainfo = "Definition"


        self.wikicode = wikicode
        self.subordinates = subordinates
        self.idx = idx
        self.header_type = header_type
        self.metainfo = header_type if metainfo is None else metainfo  # TODO: make it into an enum
        self.lvl = lvl


    @property
    def exact_header(self):
        return "=" * self.lvl + self.header_type + ("" if self.idx is None else " " + str(self.idx)) + "=" * self.lvl

    def __str__(self):
        return str(self.wikicode)

class Entry:

    def __init__(self, ety: Header, extras: List[Header]):
        assert ety or extras  # can't be blank
        assert ety is None or isinstance(ety, Header)
        self.ety = ety  # type: Header
        self.extras = extras  # type: List[Header]


class Entries:

    def __init__(self, headers: List[Header], is_multi_ety=False, did_pos=False, did_ety=False):
        assert len(headers) >= 1
        entries = []
        if is_multi_ety:  # multiple etymologies, so defns are children and l4
            assert len(headers) > 1
            for header in headers:
                assert header.idx is not None
                assert header.header_type == "Etymology"
                ety = header
                extras = []  # type: List[Header]
                for lvl4plus in wikt.sections_by_level(header.subordinates, 4):
                    lvl4 = lvl4plus[0]
                    is_defn = poscodes.is_defn(lvl4)

                    breve: str = lvl4[4:]  # len("===") == 3 # "===Pronunciation===" --> "Pronunciation===" # TODO: Code Repetition
                    header = breve[:breve.index("====")]  # "Pronunciation===" -> "Pronunciation" # TODO: Repetition
                    hdr = Header(lvl4, lvl4plus[1:], header_type=header, metainfo="Definition" if is_defn else None,
                                 lvl=4)
                    extras.append(hdr)

                entry = Entry(ety, extras)
                entries.append(entry)

        else:  # single etymology, so defns are siblings and l3
            defns = []  # type: List[Header]
            extras = []
            ety = None
            first = headers[0]  # type: Header
            if first.header_type == "Etymology":
                ety = first
            else:
                assert poscodes.is_defn(first.wikicode) == (
                            first.metainfo == "Definition")  # whether it's a poscode should already be encoded
                extras.append(first)
            for header in headers[1:]:
                assert header.idx is None
                assert header.header_type != "Etymology"
                # assert not header.subordinates
                # it's possible to have subordinates
                assert poscodes.is_defn(first.wikicode) == (
                            first.metainfo == "Definition")  # whether it's a poscode should already be encoded
                extras.append(header)
            entry = Entry(ety, extras)
            entries = [entry]
        self.entrylist = entries
        self.is_multi_ety = is_multi_ety
        self.did_pos = did_pos
        self.did_ety = did_ety
        assert self.is_multi_ety is None or self.is_multi_ety == (len(entries) > 1)

    def by_defn_id(self, index) -> Entry:
        return self.entrylist[index - 1]


def lex(dom: List[Wikicode]) -> Entries:
    sections = wikt.sections_by_level(dom, 3)
    is_multi_ety = None
    headers = []
    did_lemma = False
    for lvl3plus in sections:

        lvl3 = lvl3plus[0]
        if lvl3.startswith("===Etymology"):
            assert did_lemma is False  # Etymology should ALWAYS come before lemmas

            if lvl3.startswith("===Etymology==="):
                assert is_multi_ety is None  # There Should be Exactly one ety
                is_multi_ety = False
                assert headers == []
                h = Header(lvl3, lvl3plus[1:], header_type="Etymology")
                headers.append(h)
            else:  #
                assert is_multi_ety is not False
                assert is_multi_ety in [None, True]
                is_multi_ety = True
                breve: str = lvl3[13:]  # len("===Etymology ") == 13 # "===Etymology 1===" --> "1==="
                ety_idx = breve[:breve.index("===")]  # "1===" -> "1"
                idx = int(ety_idx)
                assert idx and type(idx) == int  # assert that it's an int
                h = Header(lvl3, lvl3plus[1:], header_type="Etymology", idx=idx)
                headers.append(h)

        else:

            # Something other than an Etymology or a POS
            breve: str = lvl3[3:]  # len("===") == 3 # "===Pronunciation===" --> "Pronunciation==="
            header = breve[:breve.index("===")]  # "Pronunciation===" -> "Pronunciation"

            defn_flag = poscodes.is_defn(lvl3)
            if defn_flag:
                assert not is_multi_ety  # if there's multiple etymologies, then the verbs SHOULD have been put in a nested level
                did_lemma = True
                h = Header(lvl3, lvl3plus[1:], header_type=header, metainfo="Definition")
                headers.append(h)
            else:
                h = Header(lvl3, lvl3plus[1:], header_type=header, metainfo="Definition" if defn_flag else None)
                # TODO: Etymology isn't always in the front; Pronunciation sometimes precedes Etymology.

    o_entries = Entries(headers, is_multi_ety=is_multi_ety, did_ety=(is_multi_ety is not None), did_pos=did_lemma)
    return o_entries


def lex2(dom: List[Wikicode]) -> List[Entry]:
    sections = wikt.sections_by_level(dom, 3)
    is_multi_ety = None

    ety = None  # type: Header
    nonetys = []  # type: List[Header]
    entries = []  # type: List[Entry]
    preety = []
    did_lemma = False
    for lvl3plus in sections:

        lvl3 = lvl3plus[0]
        if lvl3.startswith("===Etymology"):
            assert did_lemma is False  # Etymology should ALWAYS come before lemmas

            if lvl3.startswith("===Etymology==="):
                assert is_multi_ety is None  # There Should be Exactly one ety
                is_multi_ety = False
                assert not ety  # There should be exactly one ety
                ety = Header(lvl3, lvl3plus[1:])
                lvl4s = wikt.sections_by_level(lvl3plus[1:], 4)
                for lvl4plus in lvl4s:
                    lvl4 = lvl4plus[0]
                    h = Header(lvl4, lvl4plus[1:], lvl=4)
                    nonetys.append(h)
            else:  # multiple etys
                assert is_multi_ety is not False
                assert is_multi_ety in [None, True]
                is_multi_ety = True

                # package the previous
                if ety or nonetys:
                    entry = Entry(ety, nonetys)
                    entries.append(entry)

                ety = Header(lvl3, lvl3plus[1:])
                nonetys = []

        else:
            # Something other than an Etymology or a POS

            h = Header(lvl3, lvl3plus[1:])
            if poscodes.is_defn(lvl3):
                assert not is_multi_ety  # if there's multiple etymologies, then the verbs SHOULD have been put in a nested level
                assert "Definition" in h.metainfo
                did_lemma = True
            if is_multi_ety is None:
                # uhhh
                # ie. could be Pronunciation, which precedes Etymology
                # this is a difficult situation, because we don't know whether it is multi_ety or not
                # we only want to package it Only if it's single ety or zero ety, but NOT multi_ety
                # But by passing here,
                # We omit everything that occurs before the Etymology
                preety.append(h)
            elif is_multi_ety is False:
                nonetys.append(h)
    if is_multi_ety is None or is_multi_ety is False:
        assert entries == []
        nonetys = preety + nonetys


    # package remnants
    if ety or nonetys:
        entry = Entry(ety, nonetys)
        entries.append(entry)
    # o_entries = Entries(headers, is_multi_ety=is_multi_ety, did_ety=(is_multi_ety is not None), did_pos=did_lemma)
    return entries
