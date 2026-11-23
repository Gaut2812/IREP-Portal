# @irep/api-client

TypeScript types for the IREP API, generated from `apps/api/openapi.json` with `openapi-typescript@7.13.0`.

```bash
npm run generate        # after changing an API route or model (CI checks this is up to date)
```

The web app imports these as types only (`import type … from "@irep/api-client"`, via a `tsconfig` path), so nothing outside `apps/web` is bundled.
