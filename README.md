# job-posts

LinkedIn job posts for Sweden and Denmark, matched against [my CV](https://github.com/miroljub1995/cv) and tracked as JSON in `jobs/<country>/jobs.json`.

- Populated daily at 10:00 by Claude Code via the LinkedIn MCP server — see `SEARCHING.md` for how searching and match scoring work.
- Status board (GitHub Pages, served from `docs/`): change a job's status (open / applied / in-progress / denied) and it commits the change back to this repo. Requires a fine-grained personal access token with read/write access to this repo's contents.

After cloning, fetch the CV submodule:

```bash
git submodule update --init
```
