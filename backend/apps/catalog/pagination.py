from rest_framework.pagination import PageNumberPagination


class ProductListPagination(PageNumberPagination):
    # Default items per page
    page_size = 10
    # Allow clients to override page size with `?limit=`
    page_size_query_param = 'limit'
    max_page_size = 100
