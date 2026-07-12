# Obsidian Bases Reference

Bases are database-like views of vault notes stored as `.base` files (YAML). They support filters, formulas, grouping, and four view types: table, cards, list, and map.

## Workflow

1. **Create the file**: Write a `.base` file in the vault with valid YAML
2. **Define scope**: Add `filters` to select which notes appear (by tag, folder, property, or date)
3. **Add formulas** (optional): Computed properties in the `formulas` section
4. **Configure views**: One or more views (`table`, `cards`, `list`, `map`) with `order` specifying displayed properties
5. **Validate**: Ensure valid YAML, all referenced properties/formulas exist
6. **Link format**: Use standard markdown links in any text values — never wikilinks

## Schema

```yaml
# Global filters (apply to ALL views)
filters:
  and: []    # All conditions must be true
  or: []     # Any condition can be true
  not: []    # Exclude matching items

# Computed properties
formulas:
  formula_name: 'expression'

# Display name overrides
properties:
  property_name:
    displayName: "Display Name"
  formula.formula_name:
    displayName: "Formula Display Name"

# Custom summary formulas
summaries:
  custom_summary_name: 'values.mean().round(3)'

# One or more views
views:
  - type: table | cards | list | map
    name: "View Name"
    limit: 10                    # Optional: limit results
    groupBy:                     # Optional: group results
      property: property_name
      direction: ASC | DESC
    filters:                     # View-specific filters (override global)
      and: []
    order:                       # Properties to display in order
      - file.name
      - property_name
      - formula.formula_name
    summaries:                   # Map properties to summary formulas
      property_name: Average
```

## Filter Syntax

```yaml
# Single filter
filters: 'status == "done"'

# AND
filters:
  and:
    - 'status == "done"'
    - 'priority > 3'

# OR
filters:
  or:
    - 'file.hasTag("book")'
    - 'file.hasTag("article")'

# NOT
filters:
  not:
    - 'file.hasTag("archived")'

# Nested
filters:
  or:
    - file.hasTag("tag")
    - and:
        - file.hasTag("book")
        - file.hasLink("Textbook")
    - not:
        - file.hasTag("book")
        - file.inFolder("Required Reading")
```

### Filter Operators

| Operator | Description |
|----------|-------------|
| `==` | equals |
| `!=` | not equal |
| `>`, `<`, `>=`, `<=` | comparisons |
| `&&` | logical and |
| `\|\|` | logical or |
| `!` | logical not |

## Properties

### Three Types

1. **Note properties** — from frontmatter: `author` or `note.author`
2. **File properties** — file metadata: `file.name`, `file.mtime`, etc.
3. **Formula properties** — computed: `formula.my_formula`

### File Properties

| Property | Type | Description |
|----------|------|-------------|
| `file.name` | String | File name |
| `file.basename` | String | Name without extension |
| `file.path` | String | Full path |
| `file.folder` | String | Parent folder |
| `file.ext` | String | Extension |
| `file.size` | Number | Size in bytes |
| `file.ctime` | Date | Created time |
| `file.mtime` | Date | Modified time |
| `file.tags` | List | All tags |
| `file.links` | List | Internal links |
| `file.backlinks` | List | Files linking to this |
| `file.embeds` | List | Embeds in note |
| `file.properties` | Object | All frontmatter |

## Formula Syntax

```yaml
formulas:
  # Arithmetic
  total: "price * quantity"

  # Conditional
  status_icon: 'if(done, "done", "pending")'

  # String formatting
  formatted_price: 'if(price, price.toFixed(2) + " dollars")'

  # Date formatting
  created: 'file.ctime.format("YYYY-MM-DD")'

  # Days since created
  days_old: '(now() - file.ctime).days'

  # Days until due
  days_until_due: 'if(due_date, (date(due_date) - today()).days, "")'
```

### Key Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `date()` | `date(string): date` | Parse string to date |
| `now()` | `now(): date` | Current date and time |
| `today()` | `today(): date` | Current date (time = 00:00:00) |
| `if()` | `if(cond, true, false?)` | Conditional |
| `duration()` | `duration(string): duration` | Parse duration string |
| `file()` | `file(path): file` | Get file object |
| `link()` | `link(path, display?): Link` | Create a link |
| `min()` / `max()` | `min(n1, n2, ...): number` | Min/max of numbers |
| `image()` | `image(path): image` | Render image |
| `icon()` | `icon(name): icon` | Lucide icon |

### Duration Type

Subtracting dates returns a **Duration**, not a number. Access `.days`, `.hours`, `.minutes`, `.seconds` first, then apply number functions.

```yaml
# CORRECT
"(date(due_date) - today()).days"
"(now() - file.ctime).days.round(0)"

# WRONG — Duration doesn't support .round() directly
# "(now() - file.ctime).round(0)"
```

### Date Arithmetic

```yaml
# Units: y/year/years, M/month/months, d/day/days, w/week/weeks, h/hour/hours, m/minute/minutes
"now() + \"1 day\""       # Tomorrow
"today() + \"7d\""        # Week from today
```

### String Functions

`contains()`, `startsWith()`, `endsWith()`, `isEmpty()`, `lower()`, `title()`, `trim()`, `replace()`, `split()`, `slice()`, `length`

### Number Functions

`abs()`, `ceil()`, `floor()`, `round(digits?)`, `toFixed(precision)`

### List Functions

`contains()`, `filter(expr)`, `map(expr)`, `reduce(expr, init)`, `flat()`, `join(sep)`, `sort()`, `unique()`, `isEmpty()`, `length`

### File Functions

`hasTag(...tags)`, `hasLink(file)`, `hasProperty(name)`, `inFolder(folder)`, `asLink(display?)`

## Default Summary Formulas

| Name | Input | Description |
|------|-------|-------------|
| `Average` | Number | Mathematical mean |
| `Min` / `Max` | Number | Smallest / largest |
| `Sum` | Number | Sum of all |
| `Range` | Number | Max - Min |
| `Median` | Number | Median |
| `Stddev` | Number | Standard deviation |
| `Earliest` / `Latest` | Date | Earliest / latest date |
| `Checked` / `Unchecked` | Boolean | Count of true/false |
| `Empty` / `Filled` | Any | Count of empty/non-empty |
| `Unique` | Any | Count of unique values |

## View Types

### Table

```yaml
views:
  - type: table
    name: "My Table"
    order: [file.name, status, due_date]
    summaries:
      price: Sum
```

### Cards

```yaml
views:
  - type: cards
    name: "Gallery"
    order: [file.name, cover_image, description]
```

### List

```yaml
views:
  - type: list
    name: "Simple List"
    order: [file.name, status]
```

### Map

Requires latitude/longitude properties and the Maps community plugin.

## Example Bases

### Policy Review Tracker

```yaml
filters:
  and:
    - 'file.hasTag("policy")'
    - 'file.ext == "md"'

formulas:
  days_until_review: 'if(review_cycle, (date(next_review) - today()).days, "")'
  is_overdue: 'if(next_review, date(next_review) < today() && status == "current", false)'
  owner_display: 'if(owner, owner, "Unassigned")'

properties:
  formula.days_until_review:
    displayName: "Days to Review"
  formula.is_overdue:
    displayName: "Overdue?"
  formula.owner_display:
    displayName: "Owner"

views:
  - type: table
    name: "All Policies"
    order:
      - file.name
      - status
      - formula.owner_display
      - version
      - formula.days_until_review
      - formula.is_overdue
    groupBy:
      property: status
      direction: ASC
    summaries:
      formula.days_until_review: Average

  - type: table
    name: "Overdue Reviews"
    filters:
      and:
        - 'formula.is_overdue == true'
    order:
      - file.name
      - formula.owner_display
      - next_review
      - formula.days_until_review
```

### Contract Renewal Calendar

```yaml
filters:
  and:
    - 'file.hasTag("agreement")'
    - 'status != "terminated"'

formulas:
  days_to_expiry: 'if(end_date, (date(end_date) - today()).days, "")'
  renewal_urgency: 'if(days_to_expiry, if(days_to_expiry < 30, "URGENT", if(days_to_expiry < 90, "Soon", "OK")), "")'

views:
  - type: table
    name: "Active Contracts"
    order:
      - file.name
      - parties
      - end_date
      - formula.days_to_expiry
      - formula.renewal_urgency
    groupBy:
      property: formula.renewal_urgency
      direction: ASC
```

### Meeting Notes Index

```yaml
filters:
  and:
    - 'file.hasTag("meeting-transcript")'

formulas:
  day_of_week: 'date(file.basename.slice(0, 10)).format("dddd")'
  word_estimate: '(file.size / 5).round(0)'

views:
  - type: table
    name: "Recent Meetings"
    limit: 30
    order:
      - file.name
      - meeting_type
      - participants
      - formula.word_estimate
      - file.mtime
```

## Embedding Bases in Notes

```markdown
![Task Tracker](./dashboards/task-tracker.base)
![Specific View](./dashboards/task-tracker.base#Active Tasks)
```

## YAML Quoting Rules

- Single quotes for formulas containing double quotes: `'if(done, "Yes", "No")'`
- Double quotes for simple strings: `"My View Name"`
- Strings with `:`, `{`, `}`, `[`, `]`, `#`, `*`, etc. must be quoted

## Troubleshooting

**Duration math without field access**: Always access `.days`, `.hours`, etc. before `.round()`.

**Missing null checks**: Use `if()` to guard properties that may not exist on all notes.

**Referencing undefined formulas**: Every `formula.X` in `order` must have a matching entry in `formulas`.

## References

- [Bases Syntax](https://help.obsidian.md/bases/syntax)
- [Functions](https://help.obsidian.md/bases/functions)
- [Views](https://help.obsidian.md/bases/views)
