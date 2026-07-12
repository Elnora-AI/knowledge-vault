# JSON Canvas Reference

Canvas files (`.canvas`) are visual knowledge graphs following the [JSON Canvas Spec 1.0](https://jsoncanvas.org/spec/1.0/). Use them for architecture diagrams, relationship maps, project boards, flowcharts, and mind maps — all living inside the vault.

## File Structure

```json
{
  "nodes": [],
  "edges": []
}
```

## Workflow

1. Create a `.canvas` file with the base structure
2. Generate unique 16-character hex IDs for each node (`crypto.randomBytes(8).toString('hex')`)
3. Add nodes with required fields: `id`, `type`, `x`, `y`, `width`, `height`
4. Add edges referencing valid node IDs via `fromNode` and `toNode`
5. **Validate**: Parse JSON, verify all IDs unique, all edge references resolve

## Nodes

Array order determines z-index (first = bottom, last = top).

### Generic Attributes (all nodes)

| Attribute | Required | Type | Description |
|-----------|----------|------|-------------|
| `id` | Yes | string | Unique 16-char hex |
| `type` | Yes | string | `text`, `file`, `link`, or `group` |
| `x` | Yes | integer | X position (pixels, can be negative) |
| `y` | Yes | integer | Y position (pixels, can be negative) |
| `width` | Yes | integer | Width in pixels |
| `height` | Yes | integer | Height in pixels |
| `color` | No | canvasColor | `"1"`-`"6"` or hex (e.g., `"#FF0000"`) |

### Text Nodes

```json
{
  "id": "6f0ad84f44ce9c17",
  "type": "text",
  "x": 0, "y": 0,
  "width": 400, "height": 200,
  "text": "# Hello World\n\nThis is **Markdown** content."
}
```

Use `\n` for line breaks in JSON strings. Do NOT use literal `\\n`.

### File Nodes

```json
{
  "id": "a1b2c3d4e5f67890",
  "type": "file",
  "x": 500, "y": 0,
  "width": 400, "height": 300,
  "file": "Attachments/diagram.png",
  "subpath": "#Heading"
}
```

`file`: path from vault root. `subpath` (optional): heading or block reference.

### Link Nodes

```json
{
  "id": "c3d4e5f678901234",
  "type": "link",
  "x": 1000, "y": 0,
  "width": 400, "height": 200,
  "url": "https://obsidian.md"
}
```

### Group Nodes

Visual containers. Position child nodes inside the group's bounds.

```json
{
  "id": "d4e5f6789012345a",
  "type": "group",
  "x": -50, "y": -50,
  "width": 1000, "height": 600,
  "label": "Project Overview",
  "color": "4"
}
```

Optional: `background` (image path), `backgroundStyle` (`cover`, `ratio`, `repeat`).

## Edges

| Attribute | Required | Default | Description |
|-----------|----------|---------|-------------|
| `id` | Yes | - | Unique identifier |
| `fromNode` | Yes | - | Source node ID |
| `fromSide` | No | - | `top`, `right`, `bottom`, `left` |
| `fromEnd` | No | `none` | `none` or `arrow` |
| `toNode` | Yes | - | Target node ID |
| `toSide` | No | - | `top`, `right`, `bottom`, `left` |
| `toEnd` | No | `arrow` | `none` or `arrow` |
| `color` | No | - | Line color |
| `label` | No | - | Text label |

```json
{
  "id": "0123456789abcdef",
  "fromNode": "6f0ad84f44ce9c17",
  "fromSide": "right",
  "toNode": "a1b2c3d4e5f67890",
  "toSide": "left",
  "toEnd": "arrow",
  "label": "leads to"
}
```

## Colors

| Preset | Color |
|--------|-------|
| `"1"` | Red |
| `"2"` | Orange |
| `"3"` | Yellow |
| `"4"` | Green |
| `"5"` | Cyan |
| `"6"` | Purple |

Also accepts hex: `"#FF0000"`.

## Layout Guidelines

- Coordinates can be negative (canvas extends infinitely)
- `x` increases right, `y` increases down; position = top-left corner
- Space nodes 50-100px apart; 20-50px padding inside groups
- Align to grid (multiples of 20) for clean layouts

| Node Type | Suggested Width | Suggested Height |
|-----------|-----------------|------------------|
| Small text | 200-300 | 80-150 |
| Medium text | 300-450 | 150-300 |
| Large text | 400-600 | 300-500 |
| File preview | 300-500 | 200-400 |
| Link preview | 250-400 | 100-200 |

## Example Canvases

### Architecture Map

```json
{
  "nodes": [
    {
      "id": "5e6f7a8b9c0d1e2f",
      "type": "group",
      "x": 0, "y": 0,
      "width": 700, "height": 400,
      "label": "My System",
      "color": "5"
    },
    {
      "id": "6f7a8b9c0d1e2f3a",
      "type": "text",
      "x": 20, "y": 50,
      "width": 200, "height": 100,
      "text": "## API Gateway\n\nAuth + routing"
    },
    {
      "id": "7a8b9c0d1e2f3a4b",
      "type": "text",
      "x": 260, "y": 50,
      "width": 200, "height": 100,
      "text": "## Service A\n\nCore processing"
    },
    {
      "id": "8b9c0d1e2f3a4b5c",
      "type": "text",
      "x": 480, "y": 50,
      "width": 200, "height": 100,
      "text": "## Database\n\nPersistent storage"
    },
    {
      "id": "9c0d1e2f3a4b5c6d",
      "type": "file",
      "x": 20, "y": 200,
      "width": 300, "height": 150,
      "file": "reference/architecture.md"
    }
  ],
  "edges": [
    {
      "id": "a0b1c2d3e4f5a6b7",
      "fromNode": "6f7a8b9c0d1e2f3a",
      "fromSide": "right",
      "toNode": "7a8b9c0d1e2f3a4b",
      "toSide": "left",
      "label": "requests"
    },
    {
      "id": "b1c2d3e4f5a6b7c8",
      "fromNode": "7a8b9c0d1e2f3a4b",
      "fromSide": "right",
      "toNode": "8b9c0d1e2f3a4b5c",
      "toSide": "left",
      "label": "stores"
    }
  ]
}
```

### Project Board

```json
{
  "nodes": [
    {
      "id": "5e6f7a8b9c0d1e2f",
      "type": "group",
      "x": 0, "y": 0,
      "width": 300, "height": 500,
      "label": "To Do",
      "color": "1"
    },
    {
      "id": "6f7a8b9c0d1e2f3a",
      "type": "group",
      "x": 350, "y": 0,
      "width": 300, "height": 500,
      "label": "In Progress",
      "color": "3"
    },
    {
      "id": "7a8b9c0d1e2f3a4b",
      "type": "group",
      "x": 700, "y": 0,
      "width": 300, "height": 500,
      "label": "Done",
      "color": "4"
    },
    {
      "id": "8b9c0d1e2f3a4b5c",
      "type": "text",
      "x": 20, "y": 50,
      "width": 260, "height": 80,
      "text": "## Task 1\n\nImplement feature X"
    },
    {
      "id": "9c0d1e2f3a4b5c6d",
      "type": "text",
      "x": 370, "y": 50,
      "width": 260, "height": 80,
      "text": "## Task 2\n\nReview PR #123",
      "color": "2"
    }
  ],
  "edges": []
}
```

## Validation Checklist

1. All `id` values unique across nodes AND edges
2. Every `fromNode`/`toNode` references an existing node ID
3. Required fields present for each node type
4. `type` is one of: `text`, `file`, `link`, `group`
5. `fromSide`/`toSide` are one of: `top`, `right`, `bottom`, `left`
6. `fromEnd`/`toEnd` are one of: `none`, `arrow`
7. Color presets are `"1"`-`"6"` or valid hex
8. JSON is valid and parseable

## References

- [JSON Canvas Spec 1.0](https://jsoncanvas.org/spec/1.0/)
- [JSON Canvas GitHub](https://github.com/obsidianmd/jsoncanvas)
