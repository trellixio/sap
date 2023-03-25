"""
Query. 

Utils that can be used to optimize db queries and avoid redundant requests.
"""
import typing

from beanie import Document, Link, PydanticObjectId, operators
from beanie.odm.fields import ExpressionField, LinkInfo

ModelType = typing.TypeVar("ModelType", bound=Document)

RelModelType = typing.TypeVar("RelModelType", bound=Document)  # Related Model Type


async def prefetch_related(item_list: list[ModelType], to_attribute: str) -> None:
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
    related_field: LinkInfo[Document] = type(item_list[0]).get_link_fields()[to_attribute]
    related_model: Document = related_field.model_class

    def get_related_id(item_: Document) -> typing.Optional[PydanticObjectId]:
        """Return the id of the related object."""
        link: typing.Optional[Link] = getattr(item_, to_attribute)
        if link:
            return link.ref.id
        return None

    # Fetch the related attribute and map it to the each item in the item_list
    related_item_ids = list(set(get_related_id(item) for item in item_list))
    related_item_list = await related_model.find(operators.In(related_model.id, related_item_ids)).to_list()
    for item in item_list:
        related_id = get_related_id(item)
        related_item = next((rel for rel in related_item_list if rel.id == related_id), None) if related_id else None
        setattr(item, to_attribute, related_item)


async def prefetch_related_children(
    item_list: list[ModelType],
    to_attribute: str,
    related_model: type[RelModelType],
    related_attribute: str,
    filter_func: typing.Optional[
        typing.Callable[
            [list[RelModelType], ModelType],
            typing.Union[None, RelModelType, list[RelModelType]],
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
    if not filter_func:
        filter_func = lambda related_items, item: related_items

    item_ids = list(set(item.id for item in item_list))
    related_expression: ExpressionField = getattr(getattr(related_model, related_attribute), "id")
    related_item_list = await related_model.find(
        operators.In(related_expression, item_ids), sort="-doc_meta.created"
    ).to_list()

    for item in item_list:
        related_items = []
        for rel in related_item_list:
            rel_link: Link[RelModelType] = getattr(rel, related_attribute)
            if item.id == rel_link.ref.id:
                related_items.append(rel)
        setattr(item, to_attribute, filter_func(related_items=related_items, item=item))


def prepare_search_string(search_text: str) -> str:
    """Clean and reformat the search string"""
    res = search_text.strip()
    if "@" in res and not '"' in res:
        res = f'"{res}"'
    return res
