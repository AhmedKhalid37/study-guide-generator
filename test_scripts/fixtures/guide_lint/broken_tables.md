# Tables

## Mismatch Header

| A | B | C |
| --- | --- |
| 1 | 2 | 3 |

## Body Mismatch

| X | Y |
| --- | --- |
| only-one |

## Valid Table

| Name | Score |
| --- | --- |
| Ann | 90 |
| Bob | 85 |

## Orphan Separator

Some text without a header row.
| --- | --- |
| 1 | 2 |

## Malformed Separator

| P | Q |
| --- | ?? |
| 5 | 6 |
