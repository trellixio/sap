"""
Query.

Utils that can be used to optimize db queries and avoid redundant requests.
"""

from typing import Callable, Optional, Type, TypeVar, Union

from beanie import Document, PydanticObjectId, operators
from beanie.odm.fields import ExpressionField, LinkInfo

from .document import DocT
from .link import Link

RDocT = TypeVar("RDocT", bound=Document)  # Related Model Type


async def prefetch_related(item_list: list[DocT], to_attribute: str) -> None:
    """
    Optimize fetching of a related attribute of one-to-one relation.

    Fetch related attribute efficiently in order to avoid multiple queries that could kill the db.

    Example:
    ```python
    class ProductCategory(Document):
        name: str

    class Product(Document):
        category: ProductCategory
        price: float

    product_list = await Product.find().to_list()
    prefetch_related(product_list, 'category')
    ```

    If there are 70 product and 10 categories, `fetch_related` will only
    perform 1 query instead of 70 queries to retrieve category for all products.

    ```
    for product in product_list:
        print(product.category.name)
    ```
    """

    # If item_list is empty there is no need to continue.
    if not item_list:
        return

    # Find the model of the related attributed
    link_fields = type(item_list[0]).get_link_fields()
    assert link_fields
    related_field: LinkInfo = link_fields[to_attribute]
    assert issubclass(related_field.document_class, Document)
    related_model: Type[Document] = related_field.document_class

    def get_related_id(item_: Document) -> Optional[PydanticObjectId]:
        """Return the id of the related object."""
        link: Optional[Link[Document]] = getattr(item_, to_attribute)
        if link:
            return link.ref.id
        return None

    # Fetch the related attribute and map it to the each item in the item_list
    related_item_ids = list(set(get_related_id(item) for item in item_list))
    related_item_list = await related_model.find(operators.In(related_model.id, related_item_ids)).to_list()
    for item in item_list:
        link: Optional[Link[Document]] = getattr(item, to_attribute)
        if link:
            related_item = next((rel for rel in related_item_list if rel.id == link.ref.id), None)
            setattr(link, "doc", related_item)


async def prefetch_related_children(
    item_list: list[DocT],
    to_attribute: str,
    related_model: type[RDocT],
    related_attribute: str,
    filter_func: Optional[
        Callable[
            [list[RDocT], DocT],
            Union[None, RDocT, list[RDocT]],
        ]
    ] = None,
) -> None:
    """
    Optimize fetching of a related attributes of one-to-many relation.

    Fetch related attribute efficiently in order to avoid multiple queries that could kill the db.

    Example:
    ```python
    class ProductCategory(Document):
        name: str

    class Product(Document):
        category: ProductCategory
        price: float

    category_list = await ProductCategory.find().to_list()
    prefetch_related_children(
        category_list, to_attribute='products', related_model='Product', related_attribute='category'
    )
    ```

    If there are 70 product and 10 categories, `fetch_related` will only
    perform 1 query instead of 10 queries to retrieve products for all categories.

    ```python
    for category in category_list:
        for product in category.products:
            print(product.price)
    ```
    """

    def no_filter_func(related_items: list[RDocT], item: DocT) -> list[RDocT]:
        """Do not apply any filter."""
        assert item
        return related_items

    if not filter_func:
        filter_func = no_filter_func

    item_ids = list(set(item.id for item in item_list))
    related_expression: ExpressionField = getattr(getattr(related_model, related_attribute), "id")
    related_item_list = await related_model.find(
        operators.In(related_expression, item_ids), sort="-doc_meta.created"
    ).to_list()

    for item in item_list:
        related_items = []
        for rel in related_item_list:
            rel_link: Link[RDocT] = getattr(rel, related_attribute)
            if item.id == rel_link.ref.id:
                related_items.append(rel)
        setattr(item, to_attribute, filter_func(related_items, item))


def prepare_search_string(search_text: str) -> str:
    """Clean and reformat the search string."""
    res = search_text.strip()
    if "@" in res and not '"' in res:
        res = f'"{res}"'
    return res
