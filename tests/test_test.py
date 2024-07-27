import main
from eobjects.wikikey import WikiKey


def test():
    wkey = WikiKey.from_query("*per-#Proto-Indo-European")
    wkey.load_result()
    wkey.load_wikitext()
    print(wkey)


def test2():
    main.mainloop(run_queries=["*word#Proto-West Germanic"])
