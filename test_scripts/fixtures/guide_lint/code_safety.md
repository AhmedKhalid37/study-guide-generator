# Real Heading

Here is a fenced code example that contains heading-like text, a broken
table, and unbalanced math. None of it should be flagged:

```
## Not A Heading
| A | B | C |
| --- |
| 1 |
$$ unbalanced dollar inside code
\( unbalanced paren inside code
```

After the code block, normal prose continues with balanced inline $z = 2$ math.
