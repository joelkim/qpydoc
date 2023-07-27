
__all__ = [
    "__version__",
    "list_submodules",
    "walk_submodules",
    "generate_site",
]


import importlib
import os
import pkgutil
from importlib.metadata import version
from pathlib import Path
from textwrap import dedent, indent
from types import ModuleType
from typing import Any, Callable, Optional

from mypy_extensions import KwArg

__version__ = version("qpydoc")


def list_submodules(mod_fname: str) -> list[ModuleType]:
    """Yield a list of submodule ModuleInfo

    :param str mod_fname: full name string of parent module
    :return list[ModuleType]: list of submodules
    """
    mod = pkgutil.resolve_name(mod_fname)
    mod_path = os.path.dirname(mod.__file__)
    mod_info = pkgutil.iter_modules([mod_path], prefix=f"{mod_fname}.")

    submod_fnames = [mi.name for mi in mod_info]

    # filter out modules not in __all__
    if "__all__" in mod.__dict__:
        all_attrs = getattr(mod, "__all__", [])
        all_fnames = [f"{mod_fname}.{name}" for name in all_attrs]
        submod_fnames = [n for n in submod_fnames if n in all_fnames]

    # filter out modules in __exclude_submodule__
    ex_attrs = getattr(mod, "__exclude_submodule__", [])
    ex_fnames = [f"{mod_fname}.{name}" for name in ex_attrs]
    submod_fnames = [n for n in submod_fnames if n not in ex_fnames]

    # filter out modules which starts with '_'
    def no_underscore(x):
        return not x.split(".")[-1].startswith("_")
    submod_fnames = list(filter(no_underscore, submod_fnames))

    # get all modules
    all_mod = []
    for submod_fname in submod_fnames:
        try:
            mod = importlib.import_module(submod_fname)
            all_mod.append(mod)
        except Exception as e:  # noqa: W0612
            pass

    # sort by __module_order__ and name
    num_mod = len(all_mod)
    mod_order = [getattr(mod, "__module_order__", num_mod) for mod in all_mod]
    sort_data = zip(zip(mod_order, submod_fnames), all_mod)
    all_mod = [mod for _, mod in sorted(sort_data)]

    return all_mod


def walk_submodules(
    mod_fname: str,
    module_tree: list[Any] = [],
    on_mod: Optional[
        Callable[[ModuleType, KwArg()], None]] = None,
    on_submod: Optional[
        Callable[[ModuleType, ModuleType, KwArg()], None]] = None,
    **kwarg: Any
):
    """Yield ModuleInfo for all modules recursively

    :param str mod_fname: full name string of parent module
    :param list[Any] module_tree: list to collect module tree data
    :param Optional[Callable[[ModuleType, KwArg()], None]]] on_mod:
        callback for a parent module
    :param Optional[Callable[[ModuleType, ModuleType, KwArg()], None]]] on_submod:
        callback for a child submodule
    :param Any **kwarg: keyword arguments of on_mod and on_submod callbacks
    """
    mod = pkgutil.resolve_name(mod_fname)
    if on_mod is not None:
        on_mod(mod, **kwarg)

    sub_walkdata = []
    for submod in list_submodules(mod_fname):
        if on_submod is not None:
            on_submod(mod, submod, **kwarg)
        submod_fname: str = submod.__name__
        submod_data: list[Any] = []
        walk_submodules(submod_fname, submod_data, on_mod, on_submod, **kwarg)
        sub_walkdata += submod_data

    module_tree.append((mod, sub_walkdata))


def process_doc(doc: str) -> str:
    """Process docstring

    :param str doc: docstring
    :return str: converted docstring
    """
    return doc


def generate_site(
        mod_fname: str,
        prefix: Optional[str] = None,
):
    """Generate Quarto website project

    :param str mod_fname: package name
    :param Optional[str] prefix: project directory name. default to f"{mod_fname}_api"
    """
    if prefix is None:
        prefix = f"{mod_fname}_api"

    path_prefix = Path(prefix)
    if not os.path.exists(path_prefix):
        os.mkdir(path_prefix)

    def on_mod(mod: ModuleType, **kwarg: Any):
        prefix = kwarg["prefix"]
        path = Path("/".join(mod.__name__.split(".")[1:]))
        path_w_prefix = Path(prefix) / path
        if not os.path.exists(path_w_prefix):
            os.mkdir(path_w_prefix)

        with open(path_w_prefix / "index.qmd", "w") as f:
            # set docstring title
            name_list = mod.__name__.split(".")
            len_name: int = len(name_list)
            title: str = ""
            for i, n in enumerate(name_list):
                middle = "../" * (len_name - i - 1)
                pre_dot = "" if i == 0 else "."
                title += f"{pre_dot}[{n}](./{middle}index.qmd)"

            f.write("# " + title + "\n\n")

            # set docstring content
            if mod.__doc__ is not None:
                doc = process_doc(mod.__doc__)
                f.write(doc)

        container = kwarg.get("container", {})
        doc_quarto = container.get("doc_quarto", "")
        level = len(mod.__name__.split("."))
        indent_txt = " " * 4 * level
        add_doc = indent(dedent(f"""
        - section: "{mod.__name__.split('.')[-1]}"
          contents:
            - text: "MODULE DOC"
              href: {path}/index.qmd"""), indent_txt)
        container["doc_quarto"] = doc_quarto + add_doc

    doc_quarto = dedent("""
    project:
      type: website

    website:
      sidebar:
        contents:""")

    container = {"doc_quarto": doc_quarto}
    walk_submodules(
        mod_fname,
        on_mod=on_mod,  # type: ignore
        prefix=prefix,
        container=container,
    )

    with open(path_prefix / "_quarto.yml", "w") as f:
        f.writelines(container["doc_quarto"])
