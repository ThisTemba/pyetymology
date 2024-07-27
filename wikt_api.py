import warnings

import mwparserfromhell as mwp
import requests

import emulate.template2url
import queryobjects
import queryutils
from eobjects import fixins
from eobjects.wikikey import WikiKey
from langhelper import Language
from queryobjects import ThickQuery, DummyQuery
from langcode.cache import Cache
import grandalf.utils as grutils
import networkx as nx

# matplotlib.use('WXAgg')
import matplotlib.pyplot as plt

import simple_sugi, lexer

### START helper_api.py
from typing import List, Dict, Union

import mwparserfromhell

# from mwparserfromhell.wikicode import Wikicode

from etyobjects import (
    EtyRelation,
    WordRelation,
    Originator,
    LemmaRelation,
    DescentRelation,
    MissingException,
    DisrepancyError,
)
from lexer import Header

from eobjects.fixins import input

"""
!! IMPORTANT! input is modified!
"""


online = True  # TODO: online=False displays wrong versions of ety trees without throwing an exception

import os
import builtins

if (
    os.name == "nt"
):  # if we're on windows, printing unicode messes up. Only do this on the "production" version
    # sys.stdout = NullIO()
    _print = print

    def nprint(*args, **kwargs):
        pass

    builtins.print = nprint
    print = nprint


def is_in(elem, abbr_set: Dict[str, str]):
    return elem in abbr_set.keys() or elem in abbr_set.values()


def find_node_by_origin(G: nx.Graph, origin: Originator) -> Union[WordRelation, None]:
    """
    Returns the node that contains the originator; otherwise returns false
    """

    retn = []
    for node in G.nodes:
        if isinstance(node, WordRelation):
            node: WordRelation
            if node.matches_query(origin.me):
                retn.append(node)
    if len(retn) == 0:
        warnings.warn("No matching node found for origin!")
        return None
    if len(retn) > 1:
        warnings.warn("Found more than 1 match for origin! picking the first one...")
    return retn[0]


def find_node_by_query(
    GG: nx.DiGraph, query: str, warn=True
) -> Union[WordRelation, None]:
    # _ = [print(x) for x in GG.nodes]
    retn = []
    for node in GG.nodes:
        if isinstance(node, WordRelation):
            node: WordRelation
            if node.matches_query(query, warn=warn):
                retn.append(node)
        elif type(node) is Originator:
            pass
            # warnings.warn("Why is it matching the originator?")
        else:
            raise ValueError(f"node has unexpected type {type(node)}")
    if len(retn) == 0:
        warnings.warn("No matching node found for query!")
        return None
    if len(retn) > 1:
        warnings.warn("Found more than 1 match for query! picking the first one...")
    return retn[0]


def query(
    me: Union[str, WikiKey],
    query_id=0,
    mimic_input=None,
    redundance=False,
    working_G: nx.DiGraph = None,
) -> Union[ThickQuery, List[str]]:

    if not me:
        me = input(
            "Enter a query: " + me
        )  # me will usually be no-lang, so treat it as such and don't warn

    if isinstance(me, WikiKey):
        wkey = me
        result = wkey.result
        me = wkey.me
    elif isinstance(me, str):
        if (
            me.startswith("http://")
            or me.startswith("https://")
            or me.startswith("en.wiktionary.org/wiki/")
        ):
            wkey = WikiKey.from_regurl(me)  # build from a url
            result = wkey.result
            me = wkey.me  # turn the url into a standard string me
        else:
            done = False  # build from a plaintext string
            if working_G:
                node = find_node_by_query(working_G, me, warn=False)
                if node:
                    wkey = WikiKey.from_node(node)
                    if wkey:
                        # word = wkey.word
                        # biglang = wkey.Lang
                        assert wkey.qflags is None
                        wkey.qflags = queryutils.query_to_qparts(me, warn=False)[
                            2
                        ]  # merge query and node
                        done = True
            if not done:  # default condition
                wkey = WikiKey.from_query(me, warn=False)  # we permit null langs here
            result = wkey.load_result()  # this automatically throws on error
            wkey.load_wikitext(infer_lang=True)  # right here is the lang inferral
    else:
        raise TypeError(f"{me} has an unsupported type {type(me)}")
    # we take the word and lang and parse it into the corresponding wikilink
    # TODO: we don't know that the lang is Latin until after we load the page if we're autodetecting, and to load the page we need to know the word_urlify, and word_urlify must remove macrons
    # https://en.wiktionary.org/w/api.php?action=parse&page=word&prop=wikitext&formatversion=2&format=json
    # https://en.wiktionary.org/w/api.php?action=query&list=categorymembers&cmtitle=Category:English_terms_derived_from_the_Proto-Indo-European_root_*ple%E1%B8%B1-&cmprop=title

    if result.wikitype == "query" and wkey.deriv:
        # derivs = result.derivs
        # return DummyQuery(me=me, origin=origin, child_queries=derivs, with_lang=Language(langcode="en"))
        return DummyQuery(
            wkey,
            with_lang=Language(langcode="en"),
            origin=Originator(me, o_id=query_id),
            me=me,
        )
    elif result.wikitype == "parse":
        wikitext, res, dom, langname = (
            result.wikitext,
            result.wikiresponse,
            result.dom,
            result.langname,
        )
    # Here was the lang detection

    # dom, langname = reduce_to_one_lang(dom, use_lang=mimic_input if mimic_input else biglang.langname)
    if langname and langname == wkey.Lang.langname:
        pass
    else:
        raise ValueError(
            f"Discrepancy between given lang {wkey.Lang.langname} and inferred lang {langname}"
        )
    # if not wkey.Lang: # investigate the consequences of Lang switching
    # EDIT: it should be limited because wkey is never used and this merely updates the langname to always be correct
    # The only time this might backfire is if Language(langname=langname) malfunctions or is not bijective
    # the only time it fails is if wkey.Lang.langqstr changes unexpectedly

    # me = wkey.me  # word stays the same, even with the macron bs. however lang might change b/c of auto_lang.
    if not (wkey.word and langname):
        raise ValueError(f"word/lang not available. Word:{wkey.word} lang:{langname}")

    origin = Originator(wkey.me, o_id=query_id)
    return ThickQuery.from_key(
        wkey, origin
    )  # DID: transition this and ThickQuery to use Langs and thus to remember reconstr (DONE via WikiKey)


def parse_and_graph(
    _Query,
    existent_node: EtyRelation = None,
    make_mentions_sideways=False,
    cog_lang_filter=None,
) -> nx.DiGraph:
    me, word, lang, def_id = _Query.query
    dom = _Query.dom
    query_origin = _Query.origin
    biglang = _Query.biglang()
    existent_origin = (
        existent_node if existent_node else query_origin
    )  # TODO: pass replacement_origin through origin constructor to wrap and create an origin _id
    prev = existent_origin  # origin that is guaranteed already exists
    # TODO: existent node and the origin must be the same, or else they don't compose properly.
    # TODO: brainstorm workarounds. ie. OriginsTracker. TODO: finish implementing that
    new_origin = (
        query_origin
    )  # type: Originator # new_origin should have the updated o_id

    if cog_lang_filter is None:
        cog_lang_filter = None  # None for ALL
    ety_flag = False
    lemma_flag = False

    def add_node(G, node, color=None):
        assert isinstance(node, WordRelation) or isinstance(
            node, Originator
        )  # TODO: what if prev is already in graph?
        global colors
        color = colors[node.o_id] if color is None else color
        G.add_node(node, id=node.o_id, color=color)

    G = nx.DiGraph()

    if type(prev) is Originator and prev.o_id == 0:
        # True Origin
        add_node(G, prev, color="#ff0000")
    else:
        add_node(G, prev)
    # if replacement_origin is not the origin, then that means that the origin was replaced
    # by a preexisting node that was already colored
    # therefore we should not colorize it

    if type(_Query) == DummyQuery:
        _Query: DummyQuery
        childs = _Query.child_queries
        for child in childs:
            dr = DescentRelation(
                origin=_Query.origin, template=None, query_opt=child + "#English"
            )
            add_node(G, dr)
            G.add_edge(existent_origin, dr)
        return G

    entries = lexer.lex(dom)  # type: List[Entry]
    if len(entries) > 1:
        if def_id is None:
            def_id = input("Multiple definitions detected. Enter an ID: ")
            if def_id == "":
                def_id = 1
        entry = entries[
            int(def_id) - 1
        ]  # wiktionary is 1-indexed, but our lists are 0-indexed
    # for entry in entries.entrylist:
    else:
        entry = entries[0]
    # def_id = int(def_id)
    # sec = entry.main_sec

    # if sec.startswith("===Etymology===") or sec.startswith(f"===Etymology {def_id}"):
    # if entry.entry_type == "Etymology":
    ety: Header = entry.ety
    if ety:
        assert (len(entries) > 1) == (ety.idx is not None)
        # if multi_ety, then the idx should not be None
        # and vice versa: if single ety, then idx should be None
        assert ety.idx is None or ety.idx == int(
            def_id
        )  # if either there's no idx, or the idx matches, continue
        if not ety_flag:
            ety_flag = True
        else:
            raise Exception(
                "Etymology is being parsed twice? This should be impossible"
            )

        dotyet = False
        firstsentence = []
        for node in ety.wikicode.ifilter(recursive=False):  # type: mwp.wikicode.Node
            # .filter_templates(): #type: mwp.wikicode.Template
            # if etytemp

            if isinstance(node, mwp.wikicode.Template):
                etyr = EtyRelation(new_origin, node)
                # print(str(etyr))
                if not dotyet:
                    firstsentence.append(etyr)

            else:
                # print(str(node))
                if not dotyet:  # if we're in the first sentence
                    if (
                        isinstance(node, mwparserfromhell.wikicode.Text) and "." in node
                    ):  # if we reach the end
                        firstsentence.append(
                            node[: node.index(".") + 1]
                        )  # get everything up to, and including, the period
                        # tomar
                        dotyet = True
                    else:
                        firstsentence.append(
                            node
                        )  # if we haven't reached the period, we're in the middle. capture that node

        # print("1st sentence is " + repr(firstsentence))
        ancestry = []
        # prev = origin
        # start graphing
        between_text = []
        cache = Cache(4)
        for (
            token
        ) in firstsentence:  # time to analyze the immediate etymology ("ancestry")
            if token is None:
                continue
            if isinstance(token, EtyRelation):
                token: EtyRelation
                cache.put(token)

                if any(
                    is_in(token.rtype, x)
                    for x in (
                        EtyRelation.ety_abbrs,
                        EtyRelation.aff_abbrs,
                        EtyRelation.sim_abbrs,
                    )
                ):
                    # inh, der, bor, m
                    if any(
                        "+" in s for s in between_text
                    ):  # or helper_api.is_in(token.rtype, helper_api.EtyRelation.aff_abbrs):
                        prevs_parents = G.edges(nbunch=prev)
                        parnt = next(iter(prevs_parents), (None, None))[1]
                        # parnt = prev2
                        add_node(G, token)
                        G.add_edge(token, parnt)

                        # sister node
                    else:
                        add_node(G, token)
                        if prev:
                            G.add_edge(token, prev)
                    if make_mentions_sideways and is_in(
                        token.rtype, EtyRelation.sim_abbrs
                    ):
                        pass  # if a mention
                    else:
                        prev = token
                else:
                    print(token)
                between_text = []
            else:
                between_text.append(token)
    desc: Header = entry.desc
    if len(desc) > 1:
        # most Derivation sections have only 1 root
        warnings.warn(f"More than one descendant section for {_Query.me}!?")
    for l3h in desc:
        descRs = []
        prevDR = None
        for node in l3h.wikicode.ifilter(recursive=True):
            if isinstance(node, mwp.wikicode.Template):
                descR = DescentRelation(new_origin, node)
                if descR:
                    if descR.rtype == "see desc":
                        # this is a marker that tells you that it might have stuff
                        if (
                            cog_lang_filter and prevDR not in cog_lang_filter
                        ):  # if there's a whitelist, but prevDR wasn't in the whitelist
                            descRs.append(prevDR)  # add it to compensate
                    elif cog_lang_filter is None:
                        descRs.append(
                            descR
                        )  # cog_lang_filter allows all if None: aka a carte blanche
                    elif descR.langname in cog_lang_filter:
                        # otherwise, only if that langname is permissible according to the filter
                        descRs.append(descR)
                prevDR = descR
            else:
                pass
                # prevDR = node

        prev = existent_origin
        for token in descRs:
            add_node(G, token)
            # if prev: # it should
            G.add_edge(
                existent_origin, token
            )  # TODO: indention based on the level of indent in wiktionary
            if make_mentions_sideways and is_in(token.rtype, EtyRelation.sim_abbrs):
                pass  # if a mention
            else:
                pass  # prev = token

    # if sec.startswith("===Verb===") or sec.startswith(f"===Verb {def_id}"):
    # for subsec in sections_by_level(entry.subordinates, 4):
    for defn in entry.extras:  # type: Header
        assert defn is None or isinstance(defn, Header)
        if defn.metainfo != "Definition":
            continue
        lemma_rels = []
        for node in defn.wikicode.ifilter(recursive=False):
            if isinstance(node, mwp.wikicode.Template):
                node: mwp.wikicode.Template
                templ_name = node.name
                if templ_name[-3:] == " of":
                    if ety_flag:
                        raise Exception("both Ety and Lemma are being parsed?")
                    # lang = node.params[0]
                    # word = node.params[1]
                    # print(f"Found lemma?: lang: {lang} word: {word}")
                    lemma_rel = LemmaRelation(query_origin, node)
                    # print("-"+repr(subsec))
                    lemma_flag = True

                    if not any(
                        lemma_rel.matches(x) for x in lemma_rels
                    ):  # if it doesn't match any
                        lemma_rels.append(lemma_rel)
                        # Start graphing
                        add_node(G, lemma_rel)
                        if prev:
                            G.add_edge(lemma_rel, prev)
                            # prev = lemma_rel
        # Basic methodology: detect if a template ends in " of", such as "past participle of"
        # lemma_flag = True

    if not ety_flag:
        if lemma_flag:
            pass  # raise MissingException("Definition detected, but etymology not detected. (Perhaps it's lemmatized?)", missing_thing="etymology")
        else:
            raise MissingException(
                "Neither definition nor etymology detected.",
                missing_thing="definition",
                G=G,
            )
    return G


# def graph(query, wikiresponse, origin, src, word_urlify, replacement_origin=None):
def graph(
    _Query: ThickQuery, replacement_origin=None, cog_search_langs=None
) -> nx.DiGraph:
    try:
        G = parse_and_graph(
            _Query, existent_node=replacement_origin, cog_lang_filter=cog_search_langs
        )
    except MissingException as e:
        if e.missing_thing == "definition":
            warnings.warn(str(e))
            G = e.G
            # DID: soft crash
        else:
            raise e from None
    except Exception as e:
        raise e from None
    finally:
        print(_Query.wikitext_link)
        print(f"https://en.wiktionary.org/wiki/{_Query.word_urlify}")

    # print(len(G))
    assert type(G) == nx.DiGraph  # assert only 1 graph
    return G


# addition F55D3E-
colors = [
    "#B1D4E0",
    "#2E8BC0",
    "#878E88",
    "#F7CB15",
    "#76BED0",
    "#0C2D48",
    "#145DA0",
    "#1f78b4",
]  #


def draw_graph(G, simple=False, pause=False):
    print("...drawing graph...")

    if simple:
        poses = simple_sugi.pos(G)
    else:
        g = grutils.convert_nextworkx_graph_to_grandalf(G)
        from grandalf.layouts import SugiyamaLayout

        class DefaultView(object):
            w, h = 10, 10

        for v in g.V():
            v.view = DefaultView()
        sug = SugiyamaLayout(g.C[0])
        sug.init_all()  # roots=[V[0]]) #, inverted_edges=[V[4].e_to(V[0])])
        sug.draw()
        poses = {v.data: (-v.view.xy[0], -v.view.xy[1]) for v in g.C[0].sV}

    node_colors = nx.get_node_attributes(G, "color")
    if node_colors:
        nx.draw(G, pos=poses, with_labels=True, node_color=node_colors.values())
    else:
        global colors
        try:
            node_colors = {node: colors[node.o_id] for node in G.nodes}
            nx.draw(G, pos=poses, with_labels=True, node_color=node_colors.values())
        except AttributeError:
            warnings.warn("Node didn't have color?")
            nx.draw(G, pos=poses, with_labels=True)

    # x.draw_networkx_edges(G, pos=poses)

    if pause:
        plt.show()
    else:
        # plt.pause(0.01) pauses for 0.01s, and runs plt's GUI main loop
        plt.pause(0.01)
        fixins._is_plot_active = True
