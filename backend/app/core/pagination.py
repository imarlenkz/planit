from fastapi import Query


class PageParams:
    def __init__(self, page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=200)):
        self.page, self.size = page, size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
