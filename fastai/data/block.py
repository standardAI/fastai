# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/06_data.block.ipynb (unless otherwise specified).


from __future__ import annotations


__all__ = ['TransformBlock', 'CategoryBlock', 'MultiCategoryBlock', 'RegressionBlock', 'DataBlock']

# Cell
#nbdev_comment from __future__ import annotations
from ..torch_basics import *
from .core import *
from .load import *
from .external import *
from .transforms import *

# Cell
class TransformBlock():
    "A basic wrapper that links defaults transforms for the data block API"
    def __init__(self,
        type_tfms:list=None, # One or more `Transform`s
        item_tfms:list=None, # `ItemTransform`s, applied on an item
        batch_tfms:list=None, # `Transform`s or `RandTransform`s, applied by batch
        dl_type:TfmdDL=None, # Task specific `TfmdDL`, defaults to `TfmdDL`
        dls_kwargs:dict=None, # Additional arguments to be passed to `DataLoaders`
    ):
        self.type_tfms  =            L(type_tfms)
        self.item_tfms  = ToTensor + L(item_tfms)
        self.batch_tfms =            L(batch_tfms)
        self.dl_type,self.dls_kwargs = dl_type,({} if dls_kwargs is None else dls_kwargs)

# Cell
def CategoryBlock(
    vocab:list|pd.Series=None, # List of unique class names
    sort:bool=True, # Sort the classes alphabetically
    add_na:bool=False, # Add `#na#` to `vocab`
):
    "`TransformBlock` for single-label categorical targets"
    return TransformBlock(type_tfms=Categorize(vocab=vocab, sort=sort, add_na=add_na))

# Cell
def MultiCategoryBlock(
    encoded:bool=False, # Whether the data comes in one-hot encoded
    vocab:list|pd.Series=None, # List of unique class names
    add_na:bool=False, # Add `#na#` to `vocab`
):
    "`TransformBlock` for multi-label categorical targets"
    tfm = EncodedMultiCategorize(vocab=vocab) if encoded else [MultiCategorize(vocab=vocab, add_na=add_na), OneHotEncode]
    return TransformBlock(type_tfms=tfm)

# Cell
def RegressionBlock(
    n_out:int=None, # Number of output values
):
    "`TransformBlock` for float targets"
    return TransformBlock(type_tfms=RegressionSetup(c=n_out))

# Cell
from inspect import isfunction,ismethod

# Cell
def _merge_grouper(o):
    if isinstance(o, LambdaType): return id(o)
    elif isinstance(o, type): return o
    elif (isfunction(o) or ismethod(o)): return o.__qualname__
    return o.__class__

# Cell
def _merge_tfms(*tfms):
    "Group the `tfms` in a single list, removing duplicates (from the same class) and instantiating"
    g = groupby(concat(*tfms), _merge_grouper)
    return L(v[-1] for k,v in g.items()).map(instantiate)

def _zip(x): return L(x).zip()

# Cell
@docs
@funcs_kwargs
class DataBlock():
    "Generic container to quickly build `Datasets` and `DataLoaders`."
    get_x=get_items=splitter=get_y = None
    blocks,dl_type = (TransformBlock,TransformBlock),TfmdDL
    _methods = 'get_items splitter get_y get_x'.split()
    _msg = "If you wanted to compose several transforms in your getter don't forget to wrap them in a `Pipeline`."
    def __init__(self,
        blocks:list=None, # One or more `TransformBlock`s
        dl_type:TfmdDL=None, # Task specific `TfmdDL`, defaults to `block`'s dl_type or`TfmdDL`
        getters:list=None, # Getter functions applied to results of `get_items`
        n_inp:int=None, # Number of inputs
        item_tfms:list=None, # `ItemTransform`s, applied on an item
        batch_tfms:list=None, # `Transform`s or `RandTransform`s, applied by batch
        **kwargs,
    ):
        blocks = L(self.blocks if blocks is None else blocks)
        blocks = L(b() if callable(b) else b for b in blocks)
        self.type_tfms = blocks.attrgot('type_tfms', L())
        self.default_item_tfms  = _merge_tfms(*blocks.attrgot('item_tfms',  L()))
        self.default_batch_tfms = _merge_tfms(*blocks.attrgot('batch_tfms', L()))
        for b in blocks:
            if getattr(b, 'dl_type', None) is not None: self.dl_type = b.dl_type
        if dl_type is not None: self.dl_type = dl_type
        self.dataloaders = delegates(self.dl_type.__init__)(self.dataloaders)
        self.dls_kwargs = merge(*blocks.attrgot('dls_kwargs', {}))

        self.n_inp = ifnone(n_inp, max(1, len(blocks)-1))
        self.getters = ifnone(getters, [noop]*len(self.type_tfms))
        if self.get_x:
            if len(L(self.get_x)) != self.n_inp:
                raise ValueError(f'get_x contains {len(L(self.get_x))} functions, but must contain {self.n_inp} (one for each input)\n{self._msg}')
            self.getters[:self.n_inp] = L(self.get_x)
        if self.get_y:
            n_targs = len(self.getters) - self.n_inp
            if len(L(self.get_y)) != n_targs:
                raise ValueError(f'get_y contains {len(L(self.get_y))} functions, but must contain {n_targs} (one for each target)\n{self._msg}')
            self.getters[self.n_inp:] = L(self.get_y)

        if kwargs: raise TypeError(f'invalid keyword arguments: {", ".join(kwargs.keys())}')
        self.new(item_tfms, batch_tfms)

    def _combine_type_tfms(self): return L([self.getters, self.type_tfms]).map_zip(
        lambda g,tt: (g.fs if isinstance(g, Pipeline) else L(g)) + tt)

    def new(self,
        item_tfms:list=None, # `ItemTransform`s, applied on an item
        batch_tfms:list=None, # `Transform`s or `RandTransform`s, applied by batch
    ):
        self.item_tfms  = _merge_tfms(self.default_item_tfms,  item_tfms)
        self.batch_tfms = _merge_tfms(self.default_batch_tfms, batch_tfms)
        return self

    @classmethod
    def from_columns(cls,
        blocks:list =None, # One or more `TransformBlock`s
        getters:list =None, # Getter functions applied to results of `get_items`
        get_items:callable=None, # A function to get items
        **kwargs,
    ):
        if getters is None: getters = L(ItemGetter(i) for i in range(2 if blocks is None else len(L(blocks))))
        get_items = _zip if get_items is None else compose(get_items, _zip)
        return cls(blocks=blocks, getters=getters, get_items=get_items, **kwargs)

    def datasets(self,
        source, # The data source
        verbose:bool=False, # Show verbose messages
    ) -> Datasets:
        self.source = source                     ; pv(f"Collecting items from {source}", verbose)
        items = (self.get_items or noop)(source) ; pv(f"Found {len(items)} items", verbose)
        splits = (self.splitter or RandomSplitter())(items)
        pv(f"{len(splits)} datasets of sizes {','.join([str(len(s)) for s in splits])}", verbose)
        return Datasets(items, tfms=self._combine_type_tfms(), splits=splits, dl_type=self.dl_type, n_inp=self.n_inp, verbose=verbose)

    def dataloaders(self,
        source, # The data source
        path:str='.', # Data source and default `Learner` path
        verbose:bool=False, # Show verbose messages
        **kwargs
    ) -> DataLoaders:
        dsets = self.datasets(source, verbose=verbose)
        kwargs = {**self.dls_kwargs, **kwargs, 'verbose': verbose}
        return dsets.dataloaders(path=path, after_item=self.item_tfms, after_batch=self.batch_tfms, **kwargs)

    _docs = dict(new="Create a new `DataBlock` with other `item_tfms` and `batch_tfms`",
                 datasets="Create a `Datasets` object from `source`",
                 dataloaders="Create a `DataLoaders` object from `source`")

# Cell
def _short_repr(x):
    if isinstance(x, tuple): return f'({", ".join([_short_repr(y) for y in x])})'
    if isinstance(x, list): return f'[{", ".join([_short_repr(y) for y in x])}]'
    if not isinstance(x, Tensor): return str(x)
    if x.numel() <= 20 and x.ndim <=1: return str(x)
    return f'{x.__class__.__name__} of size {"x".join([str(d) for d in x.shape])}'

# Cell
def _apply_pipeline(p, x):
    print(f"  {p}\n    starting from\n      {_short_repr(x)}")
    for f in p.fs:
        name = f.name
        try:
            x = f(x)
            if name != "noop": print(f"    applying {name} gives\n      {_short_repr(x)}")
        except Exception as e:
            print(f"    applying {name} failed.")
            raise e
    return x

# Cell
from .load import _collate_types

def _find_fail_collate(s):
    s = L(*s)
    for x in s[0]:
        if not isinstance(x, _collate_types): return f"{type(x).__name__} is not collatable"
    for i in range_of(s[0]):
        try: _ = default_collate(s.itemgot(i))
        except:
            shapes = [getattr(o[i], 'shape', None) for o in s]
            return f"Could not collate the {i}-th members of your tuples because got the following shapes\n{','.join([str(s) for s in shapes])}"

# Cell
@patch
def summary(self:DataBlock,
    source, # The data source
    bs:int=4, # The batch size
    show_batch:bool=False, # Call `show_batch` after the summary
    **kwargs, # Additional keyword arguments to `show_batch`
):
    "Steps through the transform pipeline for one batch, and optionally calls `show_batch(**kwargs)` on the transient `Dataloaders`."
    print(f"Setting-up type transforms pipelines")
    dsets = self.datasets(source, verbose=True)
    print("\nBuilding one sample")
    for tl in dsets.train.tls:
        _apply_pipeline(tl.tfms, get_first(dsets.train.items))
    print(f"\nFinal sample: {dsets.train[0]}\n\n")

    dls = self.dataloaders(source, bs=bs, verbose=True)
    print("\nBuilding one batch")
    if len([f for f in dls.train.after_item.fs if f.name != 'noop'])!=0:
        print("Applying item_tfms to the first sample:")
        s = [_apply_pipeline(dls.train.after_item, dsets.train[0])]
        print(f"\nAdding the next {bs-1} samples")
        s += [dls.train.after_item(dsets.train[i]) for i in range(1, bs)]
    else:
        print("No item_tfms to apply")
        s = [dls.train.after_item(dsets.train[i]) for i in range(bs)]

    if len([f for f in dls.train.before_batch.fs if f.name != 'noop'])!=0:
        print("\nApplying before_batch to the list of samples")
        s = _apply_pipeline(dls.train.before_batch, s)
    else: print("\nNo before_batch transform to apply")

    print("\nCollating items in a batch")
    try:
        b = dls.train.create_batch(s)
        b = retain_types(b, s[0] if is_listy(s) else s)
    except Exception as e:
        print("Error! It's not possible to collate your items in a batch")
        why = _find_fail_collate(s)
        print("Make sure all parts of your samples are tensors of the same size" if why is None else why)
        raise e

    if len([f for f in dls.train.after_batch.fs if f.name != 'noop'])!=0:
        print("\nApplying batch_tfms to the batch built")
        b = to_device(b, dls.device)
        b = _apply_pipeline(dls.train.after_batch, b)
    else: print("\nNo batch_tfms to apply")

    if show_batch: dls.show_batch(**kwargs)