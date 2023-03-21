"""
Query. 

Utils that can be used to optimize db queries and avoid redundant requests.
"""
import typing

from beanie import Document, Link, PydanticObjectId, operators


async def fetch_related(item_list: list[Document], related_model: type[Document], field_name: str) -> None:
    """
    Optimize fetching of a related attribute.

    Fetch related attribute efficiently in order to avoid multiple queries that could kill the db.

    Example:

    ```python
    class Category(Document):
        name: str

    class Product(Document):
        product_category: Category
        price: float

    product_list = await Product.find()
    fetch_related(product_list, Category, 'product_category')
    ```

    If there are 70 product and 10 categories, `fetch_related` will only
    perform 1 query instead of 70 queries to retrieve category for all products.
    """

    def get_related_id(item_: Document) -> typing.Optional[PydanticObjectId]:
        """Return the id of the related object."""
        link: typing.Optional[Link] = getattr(item_, field_name)
        if link:
            return link.ref.id
        return None

    related_item_ids = list(set(get_related_id(item) for item in item_list))
    related_item_list = await related_model.find(operators.In(related_model.id, related_item_ids)).to_list()
    for item in item_list:
        related_id = get_related_id(item)
        related_item = next(rel for rel in related_item_list if rel.id == related_id) if related_id else None
        setattr(item, field_name, related_item)


async def fetch_related_reverse_attribute(
    item_list: list[Document], related_model: type[Document], field_name: str, link_name: str
) -> None:
    """
    Optimize fetching of a reverse related attribute.

    Fetch related reverse attribute efficiently in order to avoid multiple queries that could kill the db.
    Can only be used for `1-to-1` relations

    Example:
    ```python
    class ProductMeta(Document):
        name: str

    class Product(Document):
        meta: ProductMeta
        price: float

    product_list = await Product.find()
    fetch_related(product_list, Category, 'product_category')
    ```

    If there are 70 product and 10 categories, `fetch_related` will only
    perform 1 query instead of 70 queries to retrieve category for all products.
    """
    items_ids = list(set(x.id for x in item_list))
    related_item_list = await related_model.find(
        operators.In(getattr(related_model, link_name).id, items_ids)
    ).to_list()
    for item in item_list:
        related_item = None
        for rel in related_item_list:
            rel_link: Link[Document] = getattr(rel, link_name)
            if item.id == rel_link.ref.id:
                related_item = rel

        setattr(item, field_name, related_item)
