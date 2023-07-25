
__all__ = [
    "__version__",
    "list_submodule",
]


import importlib
import os
import pkgutil
import types
from importlib.metadata import version

__version__ = version("qpydoc")


def list_submodule(mod_fname: str) -> list[types.ModuleType]:
    """get a list of submodules from module full name

    :param str mod_fname: module full name string
    :return list[types.ModuleType]: list of submodules
    """
    module = pkgutil.resolve_name(mod_fname)
    module_path = os.path.dirname(module.__file__)
    modinfo = pkgutil.iter_modules([module_path], prefix=f"{mod_fname}.")

    # filter out modules not in __all__
    if "__all__" in module.__dict__:
        all_attrs = getattr(module, "__all__")
        all_modfname = [f"{mod_fname}.{name}" for name in all_attrs]
        all_modinfo = [mi for mi in modinfo if mi.name in all_modfname]
        all_modfname = [mi.name for mi in all_modinfo]
    else:
        all_modfname = [mi.name for mi in modinfo]

    # get all modules
    all_mod = []
    for fname in all_modfname:
        try:
            mod = importlib.import_module(fname)
            all_mod.append(mod)
        except Exception as e:  # noqa: W0612
            pass

    # sort by __module_order__ and name
    num_mod = len(all_mod)
    mod_order = [getattr(mod, "__module_order__", num_mod) for mod in all_mod]
    sort_data = zip(zip(mod_order, all_modfname), all_mod)
    all_mod = [mod for _, mod in sorted(sort_data)]

    return all_mod
