
__all__ = [
    "__version__",
    "list_submodules",
    "walk_submodules",
]


import importlib
import os
import pkgutil
import types
from importlib.metadata import version
from typing import Any, Callable

__version__ = version("qpydoc")


def list_submodules(mod_fname: str) -> list[types.ModuleType]:
    """Yields a list of submodule ModuleInfo

    :param str mod_fname: full name string of parent module
    :return list[types.ModuleType]: list of submodules
    """
    mod = pkgutil.resolve_name(mod_fname)
    mod_path = os.path.dirname(mod.__file__)
    mod_info = pkgutil.iter_modules([mod_path], prefix=f"{mod_fname}.")

    # filter out modules not in __all__
    if "__all__" in mod.__dict__:
        all_attrs = getattr(mod, "__all__")
        all_submod_fname = [f"{mod_fname}.{name}" for name in all_attrs]
        all_submod_info = [
            mi for mi in mod_info if mi.name in all_submod_fname]
        all_submod_fname = [mi.name for mi in all_submod_info]
    else:
        all_submod_fname = [mi.name for mi in mod_info]

    # filter out modules which starts with '_'
    def no_underscore(x):
        return not x.split(".")[-1].startswith("_")
    all_submod_fname = list(filter(no_underscore, all_submod_fname))

    # get all modules
    all_mod = []
    for submod_fname in all_submod_fname:
        try:
            mod = importlib.import_module(submod_fname)
            all_mod.append(mod)
        except Exception as e:  # noqa: W0612
            pass

    # sort by __module_order__ and name
    num_mod = len(all_mod)
    mod_order = [getattr(mod, "__module_order__", num_mod) for mod in all_mod]
    sort_data = zip(zip(mod_order, all_submod_fname), all_mod)
    all_mod = [mod for _, mod in sorted(sort_data)]

    return all_mod


def walk_submodules(
    mod_fname: str,
    walkdata: list[Any] = [],
    on_mod: Callable = lambda mod: None,
    on_submod: Callable = lambda mod, submod: None,
):
    """Yields ModuleInfo for all modules recursively

    :param str mod_fname: full name string of parent module
    :param list[Any] walkdata: list to collect data
    :param Callable on_mod: called for a parent module
    :param Callable on_submod: called for a child module
    """
    mod = pkgutil.resolve_name(mod_fname)
    on_mod(mod)

    sub_walkdata = []
    for submod in list_submodules(mod_fname):
        on_submod(mod, submod)
        submod_fname: str = submod.__name__
        submod_data: list[Any] = []
        walk_submodules(submod_fname, submod_data, on_mod, on_submod)
        sub_walkdata += submod_data

    walkdata.append((mod, sub_walkdata))
