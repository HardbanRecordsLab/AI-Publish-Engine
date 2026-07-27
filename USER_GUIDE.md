# User Guide — AI Publish Engine

Welcome to the AI Publish Engine — a powerful tool for generating ebooks, websites, landing pages, and blog posts using AI.

---

## Main Page (index.html)

The main interface is available at the root URL (/).

### Content Specs Sidebar

On the left side, configure your content specifications:

| Field | Description |
|-------|-------------|
| **Topic** | The subject of your content (e.g., \ Python for Beginners\) |
| **Audience** | Target reader (e.g., \beginners\, \developers\, \children\) |
| **Tone** | Writing style (e.g., \professional\, \casual\, \humorous\) |
| **Language** | Output language (e.g., English, Polish, Spanish) |
| **Sections** | Number of chapters/sections to generate |
| **Keywords** | SEO keywords to include throughout the content |

### Output Types

Choose what type of content to generate:

- **Ebook** — Full-length book with chapters, formatted for distribution
- **Website** — Multi-page HTML website structure
- **Landing Page** — Single-page promotional landing page
- **Blog Post** — Single article/blog post

### Template Selection (50 Themes)

Choose from **50 built-in themes** that control the visual appearance —
this list is generated from the theme files actually shipped with the
app (`GET /api/themes`), not hand-maintained, so it can't drift out of
sync with reality the way this section previously did. The same palettes
also drive the color/font styling for website, landing-page, blog-post,
and interactive-book output, not just ebooks.

- **AI & Tech**, **Academic Press**, **Agency Premium**, **Architecture
  Structural**, **Blog Editorial**, **Business Pro**, **Classic Book**,
  **Cookbook**, **Corporate Pro**, **Creative Studio**, **Cyberpunk**,
  **Dark Premium**, **Docs Clear**, **Education**, **Fantasy Realm**,
  **Fashion Chic**, **Financial**, **Fitness Power**, **Future Forward**,
  **Government Formal**, **Health & Wellness**, **Interview
  Conversational**, **Kids Playful**, **Landing Launch**, **Leadgen
  Punch**, **Legal Counsel**, **Listicle Punchy**, **Luxury**,
  **Magazine**, **Medical Clean**, **Minimal Pro**, **Modern Edge**,
  **Music**, **Nature Eco**, **Newsletter Friendly**, **Nonprofit Hope**,
  **Podcast Audio**, **Portfolio Showcase**, **Product Crisp**, **Real
  Estate**, **Retro Vintage**, **SaaS Product**, **Sci-Fi Frontier**,
  **Startup**, **Storyteller**, **Technical Blueprint**, **Travel**,
  **Tutorial Friendly**, **Wedding Elegance**, **Wellness Calm**

Each theme defines its own color palette, typography, and cover style.
Palettes are adapted from established MIT-licensed open-source color
systems (Open Color, Nord, Catppuccin, Dracula, Solarized) paired with
OFL-licensed Google Fonts. If you need a look that isn't covered by
these 50, use **AI Theme Generator** on the Generator screen to describe
a custom theme in plain language instead of picking from the list.

### AI Provider Selection

Select your preferred AI provider:

| Provider | Models Available |
|----------|-----------------|
| **OpenRouter** | Access to multiple models via single API |
| **Groq** | Fast inference models |
| **Gemini** | Google's Gemini models |
| **Mistral** | Mistral AI models |
| **OpenAI** | GPT-4, GPT-3.5-turbo |

### Generate Button

Click **Generate** to create your content. The system will:

1. Queue a generation job
2. Show real-time progress
3. Notify you when complete
4. Open the result for preview/download

---

## Admin Page (admin.html)

Access the admin dashboard at /admin.

### Job List

View all generation jobs with:

- **Status** — pending, running, completed, failed, cancelled
- **Progress** — percentage bar for running jobs
- **Type** — ebook, website, landing page, blog post
- **Created** — timestamp
- **Provider** — which AI provider was used

### Job Management

| Action | Description |
|--------|-------------|
| **Cancel** | Stop a running/pending job |
| **Delete** | Remove a job and its files permanently |
| **Retry** | Re-run a failed or cancelled job |

### Job Export

Each completed job can be exported in multiple formats (depending on output type):
- EPUB, PDF, MOBI, HTML, DOCX, TXT

---

## Routes Available via Browser

### Chapter Editor — /api/editor/{job_id}/chapters

A **WYSIWYG** (What You See Is What You Get) editor for reviewing and editing generated chapters before final export.

Features:
- Rich text editing per chapter
- Add/remove/reorder chapters
- Preview changes in real-time
- Save drafts

### Reader View — /api/preview/{job_id} and /api/reader/{job_id}

Two reading interfaces for viewing generated books:

- **Preview** — Clean reading view with pagination
- **Reader** — Full-featured reader with:
  - Table of contents sidebar
  - Font size adjustment
  - Theme toggle (light/dark)
  - Progress tracking
  - Bookmark support

### Download — /api/download/{job_id}

Download generated files. Available formats depend on the output type and configuration.

### Embeddable Book — /api/embed/{job_id}

An **embeddable** version of your book that can be inserted into any website via an <iframe>:

`html
<iframe src=\https://your-domain.com/api/embed/ -encodedCommand agBvAGIAXwBpAGQA \ width=\800\ height=\600\></iframe>
`

---

## Publishing & Advanced Features

### Marketing Content Generation

Generate promotional materials for your book:
- Sales copy / blurbs
- Social media posts
- Email marketing sequences
- SEO metadata
- Amazon KDP product descriptions

### Translation

Translate your generated content into **multiple languages** while preserving formatting and structure.

### AI Writing Coach

Get real-time writing feedback and suggestions:
- Style improvements
- Readability analysis
- Structural recommendations
- Vocabulary enhancement
- Sentence flow optimization

### Proofreading & Originality Check

- Grammar and spelling correction
- Plagiarism / originality scan
- Consistency checking
- Factual accuracy review suggestions

### Beta Reader (5 Personas)

Get feedback from **5 simulated beta readers** with different personas:
1. **The Casual Reader** — general enjoyment and flow
2. **The Expert** — technical accuracy and depth
3. **The Editor** — grammar, structure, clarity
4. **The Skeptic** — plot holes, logical issues
5. **The Fan** — engagement and emotional impact

### KDP Format Checker

Validate your ebook against **Amazon KDP** formatting requirements:
- Table of contents format
- Metadata (title, author, ISBN)
- Internal linking structure
- Image resolution / DPI
- File size limits
- Cover specifications

### Book Series Management

Organize your books into **series**:
- Create series with description and cover
- Add/remove books from series
- Auto-generate \Also by this author\ pages
- Series-level metadata for Amazon

### Book Launch Page Generator

Create a **professional launch page** for your upcoming book:
- Pre-order / waitlist signup
- Chapter excerpts
- Author bio
- Social proof / testimonials
- Countdown timer
- Email capture

### Print-Ready PDF

Generate a **print-ready PDF** suitable for print-on-demand services:
- Proper page sizes (trim)
- Bleed areas (3mm)
- Crop marks
- CMYK color space
- Spine width calculation
- Internal margins / gutter

### Revenue Dashboard

Track your earnings with a **localStorage-based dashboard** on the frontend:
- Add manual income entries
- Organize by book / platform / month
- View totals and charts
- Export data to CSV
