
__all__ = [
    "__version__",
    "list_submodules",
    "walk_submodules",
    "generate_site",
]

import importlib
import os
import pkgutil
import re
from copy import copy
from gettext import translation
from importlib.metadata import version
from inspect import _empty, cleandoc, signature
from pathlib import Path
from textwrap import dedent, indent
from types import ModuleType
from typing import Any, Callable, Optional
from unicodedata import east_asian_width

from autopep8 import fix_code
from mypy_extensions import KwArg

__version__ = version("qpydoc")

i18n: Any


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
        Callable[[ModuleType, KwArg()], None]] = None,  # type: ignore
    on_submod: Optional[
        Callable[[ModuleType, ModuleType, KwArg()], None]] = None,  # type: ignore
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
        on_mod(mod, **kwarg)  # type: ignore

    sub_walkdata = []
    for submod in list_submodules(mod_fname):
        if on_submod is not None:
            on_submod(mod, submod, **kwarg)  # type: ignore
        submod_fname: str = submod.__name__
        submod_data: list[Any] = []
        walk_submodules(submod_fname, submod_data, on_mod, on_submod, **kwarg)
        sub_walkdata += submod_data

    module_tree.append((mod, sub_walkdata))


def process_doctest(doc: str) -> str:
    processed_doc = copy(doc)

    pattern_doctest = re.compile(
        r"(?P<code>^(?P<indent>[ \t]*)>>> \S+.*(\n(?P=indent)\.\.\.\s+.*$)*)"
        r"(?P<output>(\n(?P=indent)(?!>>>)+.*$|\n(?!\n\n))*)",
        flags=re.MULTILINE)

    for m in pattern_doctest.finditer(doc):
        indent_str = m.groupdict()["indent"]
        org_code = str(m.groupdict().get("code", ""))

        # remove output
        output = m.groupdict().get("output")
        if output is not None:
            processed_doc = processed_doc.replace(output.strip(), "")
            org_code = org_code.replace(output.strip(), "")

        # remove >>> and ...
        code_str = org_code.replace(">>> ", "").replace("... ", "")

        # convert to fenced code
        fenced_code = indent_str + \
            "```{python}\n" + code_str + "\n" + indent_str + "```"
        processed_doc = processed_doc.replace(org_code, fenced_code)

    return processed_doc


def process_rst_args(doc: str, func: Callable) -> str:
    processed_doc = copy(doc)

    # process spaces in Literal brackets
    m = re.search(r"(list|tuple|Literal|Union|Optional)\[.*?\]", processed_doc)
    if m is not None:
        org_str = m.group()
        rep_str = org_str.replace(" ", "")
        processed_doc = processed_doc.replace(org_str, rep_str)

    # prcess params
    m = re.search(
        r"^[ \t]*:(param|return|raises)\s+.*:",
        processed_doc, flags=re.MULTILINE
    )

    if m is not None:
        sig = signature(func)
        sig_str = func.__name__

        if len(sig.parameters) > 0:
            sig_str += "(\n"
            for v in sig.parameters.values():
                sig_str += f"    {v},\n"
            sig_str += ")"
        else:
            sig_str += "()"

        if sig.return_annotation is not _empty:
            ret_type = str(sig.return_annotation)
            ret_type = ret_type.lstrip("<class '").rstrip("'>")
            sig_str += f" -> {ret_type}\n"
        else:
            sig_str += "\n"

        sig_str = fix_code(sig_str)
        idx = m.start()
        processed_doc = \
            processed_doc[:idx] + \
            f"\n```python\n{sig_str}```\n" + \
            processed_doc[idx:]

        def repl(m):
            d = m.groupdict()
            indent = d.get("indent", "")
            arg_comment = d.get("comment", "")
            arg_name = d.get("name", "")
            arg_type = d.get("type", "")

            global i18n
            i18n_return = i18n.gettext("RETURN")
            i18n_raise = i18n.gettext("RAISE")

            field_type = d.get("field_type", "")
            if field_type == "param":
                return f"{indent}- `{arg_name}` (`{arg_type}`):{arg_comment}"
            elif field_type == "return":
                return f"{indent}- {i18n_return} (`{arg_type}`):{arg_comment}"
            elif field_type == "raises":
                return f"{indent}- {i18n_raise} (`{arg_type})`:{arg_comment}"
            else:
                return ""

        processed_doc = re.sub(
            r"^(?P<indent>[ \t]*):"
            r"(?P<field_type>param|return|raises)\s+"
            r"(?P<type>\S+)(\s+(?P<name>\S+))?:(?P<comment>.*)$",
            repl, processed_doc, flags=re.MULTILINE)

    return processed_doc


def calc_eastasian_width(txt: str) -> int:
    """calcalate width of east asian string

    :param str txt: east asian string
    :return int: width of east asian string
    """
    len_str = 0
    for ch in txt:
        if east_asian_width(ch) in ["W", "F"]:
            len_str += 2
        else:
            len_str += 1
    return len_str


def generate_site(
        mod_fname: str,
        prefix: Optional[str] = None,
        locale: Optional[str] = None,
        sidebar_width: Optional[str] = None,
):
    """Generate Quarto website project

    :param str mod_fname: package name
    :param Optional[str] prefix: project directory name. default to f"{mod_fname}_api"
    :param Optional[str] locale: locale. default to "en_US"
    :param Optional[str] sidebar_width: sidebar width. default to "350px"
    """
    if locale is None:
        locale = "en_US"
    localedir = Path(os.path.dirname(os.path.abspath(__file__))) / "locales"

    global i18n
    i18n = translation("messages", localedir=localedir, languages=[locale])

    if sidebar_width is None:
        sidebar_width = "350px"

    if prefix is None:
        prefix = f"{mod_fname}_api"

    path_prefix = Path(prefix)
    if not os.path.exists(path_prefix):
        os.mkdir(path_prefix)

    def on_mod(mod: ModuleType, **kwarg: Any):
        mod_name = mod.__name__
        mod_name_list = mod_name.split(".")
        len_mod_name = len(mod_name_list)
        mod_path = Path("/".join(mod_name_list[1:]))

        # create directory
        prefix = kwarg["prefix"]
        dir_path = Path(prefix) / mod_path
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)

        # get function list
        max_fname = 0
        max_fshortdoc = 0
        all_funcs = []
        for fname in getattr(mod, "__all__", []):
            func = getattr(mod, fname, None)
            if callable(func):
                fdocs = getattr(func, "__doc__")
                if fdocs is None:
                    fshortdoc = fname
                else:
                    fshortdoc = fdocs.split("\n")[0]

                max_fname = max(max_fname, len(fname))
                len_fshortdoc = calc_eastasian_width(fshortdoc)
                max_fshortdoc = max(max_fshortdoc, len_fshortdoc)

                all_funcs.append((func, fname, fshortdoc))

        max_fname += 2

        # create index file
        mod_filename = "index.qmd"
        mod_filepath = dir_path / mod_filename
        mod_filepath_wo_prefix = mod_path / mod_filename

        with open(mod_filepath, "w") as f_mod:
            # set module title
            mod_title: str = ""
            for i, n in enumerate(mod_name_list):
                middle = "../" * (len_mod_name - i - 1)
                pre_dot = "" if i == 0 else "."
                mod_title += f"{pre_dot}[{n}](./{middle}{mod_filename})"

            f_mod.write(f"# {mod_title}\n\n")

            # set module content
            if mod.__doc__ is not None:
                doc = cleandoc(mod.__doc__)
                doc = process_doctest(doc)
                f_mod.write(doc)

            # append function list
            if len(all_funcs) > 0:
                i18n_function_list = i18n.gettext("function list")
                f_mod.write(f"\n\n### {i18n_function_list}\n\n")
                i18n_function_name = i18n.gettext("function name")
                i18n_function_comment = i18n.gettext("function comment")
                f_mod.write(
                    f"| {i18n_function_name:{max_fname}} "
                    f"| {i18n_function_comment:{max_fshortdoc}} |\n"
                )
                f_mod.write(
                    f"|:{'-' * max_fname}-"
                    f"|:{'-' * max_fshortdoc}-|\n"
                )
                for _, fname, fshortdoc in all_funcs:
                    len_sp = max_fshortdoc - calc_eastasian_width(fshortdoc)
                    f_mod.write(
                        f"| {'`' + fname + '`':{max_fname}} "
                        f"| {fshortdoc + ' ' * len_sp} |\n"
                    )
                f_mod.write("\n")

        container = kwarg.get("container", {})
        doc_quarto = container.get("doc_quarto", "")

        mod_doc_indent = " " * 4 * len_mod_name
        i18n_module_doc = i18n.gettext("MODULE DOC")
        mod_doc = indent(dedent(f"""
        - section: "{mod_name}"
          contents:
            - text: "{i18n_module_doc}"
              href: {mod_filepath_wo_prefix}"""), mod_doc_indent)

        container["doc_quarto"] = doc_quarto + mod_doc

        if len(all_funcs) > 0:
            func_sect_indent = mod_doc_indent + " " * 4
            i18n_functions = i18n.gettext("FUNCTIONS")
            func_doc = indent(dedent(f"""
            - section: "{i18n_functions}"
              contents:"""), func_sect_indent)

            for func, fname, fshortdoc in all_funcs:
                func_filename = f"{fname}.qmd"
                func_filepath = dir_path / func_filename
                func_filepath_wo_prefix = mod_path / func_filename

                func_indent = func_sect_indent + " " * 2
                func_doc += indent(dedent(f"""
                - text: {fname}
                  href: {func_filepath_wo_prefix}"""), func_indent)

                with open(func_filepath, "w") as f_func:
                    # set function title
                    func_title = mod_title + f".[{fname}](./{func_filename})"
                    f_func.write(f"# {func_title}\n\n")

                    # set function content
                    if func.__doc__ is not None:
                        doc = cleandoc(func.__doc__)
                        doc = process_doctest(doc)
                        doc = process_rst_args(doc, func)
                        f_func.write(doc)

            container["doc_quarto"] = container["doc_quarto"] + func_doc

    # create _quarto content
    doc_quarto = dedent(f"""
    project:
      type: website
    execute:
      echo: true
    format:
      html:
        grid:
          sidebar-width: {sidebar_width}
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
