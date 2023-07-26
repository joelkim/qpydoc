
__all__ = [
    "__version__",
    "list_submodules",
    "walk_submodules",
]


import importlib
import os
import pkgutil
from importlib.metadata import version
from types import ModuleType
from typing import Any, Callable, Optional

from mypy_extensions import Arg, KwArg, VarArg

__version__ = version("qpydoc")


def list_submodules(mod_fname: str) -> list[ModuleType]:
    """Yields a list of submodule ModuleInfo

    :param str mod_fname: full name string of parent module
    :return list[ModuleType]: list of submodules
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
    on_mod: Optional[
        Callable[[ModuleType, KwArg()], None]] = None,
    on_submod: Optional[
        Callable[[ModuleType, ModuleType, KwArg()], None]] = None,
    **kwarg: Any
):
    """Yields ModuleInfo for all modules recursively

    :param str mod_fname: full name string of parent module
    :param list[Any] walkdata: list to collect data
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

    walkdata.append((mod, sub_walkdata))
