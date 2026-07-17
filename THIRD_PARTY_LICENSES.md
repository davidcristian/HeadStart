# Third-party licenses

HeadStart itself is licensed under [`LICENSE`](LICENSE) (SSPL 1.0).
This file lists **third-party** packages bundled into the conveyed backend and
frontend container images so upstream MIT / BSD / Apache / LGPL (and similar)
attribution terms are preserved for self-host and distribution.

Regenerate after dependency bumps:

```bash
just generate-third-party-licenses
```

Generated at `2026-07-17T18:17:30Z` (UTC).

## Backend runtime (`backend/requirements.txt`)

Packages installed into the API / beat image (and the shared base of the worker
image) from the hashed runtime lockfile.

| Name               | Version     | License                              | URL                                                                  |
|--------------------|-------------|--------------------------------------|----------------------------------------------------------------------|
| Mako               | 1.3.12      | MIT License                          | https://www.makotemplates.org/                                       |
| MarkupSafe         | 3.0.3       | BSD-3-Clause                         | https://github.com/pallets/markupsafe/                               |
| PyJWT              | 2.13.0      | MIT                                  | https://github.com/jpadilla/pyjwt                                    |
| PyYAML             | 6.0.3       | MIT License                          | https://pyyaml.org/                                                  |
| SQLAlchemy         | 2.0.51      | MIT                                  | https://www.sqlalchemy.org                                           |
| alembic            | 1.18.5      | MIT                                  | https://alembic.sqlalchemy.org                                       |
| amqp               | 5.3.1       | BSD License                          | http://github.com/celery/py-amqp                                     |
| annotated-doc      | 0.0.4       | MIT                                  | https://github.com/fastapi/annotated-doc                             |
| annotated-types    | 0.7.0       | MIT License                          | https://github.com/annotated-types/annotated-types                   |
| anyio              | 4.14.1      | MIT                                  | https://anyio.readthedocs.io/en/stable/versionhistory.html           |
| bcrypt             | 5.0.0       | Apache Software License              | https://github.com/pyca/bcrypt/                                      |
| billiard           | 4.2.4       | BSD License                          | https://github.com/celery/billiard                                   |
| celery             | 5.6.3       | BSD-3-Clause                         | https://docs.celeryq.dev/                                            |
| certifi            | 2026.6.17   | Mozilla Public License 2.0 (MPL 2.0) | https://github.com/certifi/python-certifi                            |
| cffi               | 2.1.0       | MIT-0                                | https://cffi.readthedocs.io/en/latest/whatsnew.html                  |
| charset-normalizer | 3.4.9       | MIT                                  | https://github.com/jawah/charset_normalizer/blob/master/CHANGELOG.md |
| click              | 8.4.2       | BSD-3-Clause                         | https://github.com/pallets/click/                                    |
| click-didyoumean   | 0.3.1       | MIT License                          | https://github.com/click-contrib/click-didyoumean                    |
| click-plugins      | 1.1.1.2     | BSD License                          | https://github.com/click-contrib/click-plugins                       |
| click-repl         | 0.3.0       | MIT                                  | https://github.com/untitaker/click-repl                              |
| cryptography       | 49.0.0      | Apache-2.0 OR BSD-3-Clause           | https://github.com/pyca/cryptography                                 |
| dnspython          | 2.8.0       | ISC License (ISCL)                   | https://www.dnspython.org                                            |
| email-validator    | 2.3.0       | The Unlicense (Unlicense)            | https://github.com/JoshData/python-email-validator                   |
| fastapi            | 0.139.0     | MIT                                  | https://github.com/fastapi/fastapi                                   |
| greenlet           | 3.5.3       | MIT AND PSF-2.0                      | https://greenlet.readthedocs.io                                      |
| h11                | 0.16.0      | MIT License                          | https://github.com/python-hyper/h11                                  |
| httpcore           | 1.0.9       | BSD-3-Clause                         | https://www.encode.io/httpcore/                                      |
| httptools          | 0.8.0       | MIT                                  | https://github.com/MagicStack/httptools                              |
| httpx              | 0.28.1      | BSD License                          | https://github.com/encode/httpx                                      |
| idna               | 3.18        | BSD-3-Clause                         | https://github.com/kjd/idna                                          |
| kombu              | 5.6.2       | BSD-3-Clause                         | https://kombu.readthedocs.io                                         |
| packaging          | 26.2        | Apache-2.0 OR BSD-2-Clause           | https://github.com/pypa/packaging                                    |
| prometheus_client  | 0.25.0      | Apache-2.0 AND BSD-2-Clause          | https://github.com/prometheus/client_python                          |
| prompt_toolkit     | 3.0.52      | BSD License                          | https://github.com/prompt-toolkit/python-prompt-toolkit              |
| psycopg            | 3.3.4       | LGPL-3.0-only                        | https://psycopg.org/                                                 |
| psycopg-binary     | 3.3.4       | LGPL-3.0-only                        | https://psycopg.org/                                                 |
| pycparser          | 3.0         | BSD-3-Clause                         | https://github.com/eliben/pycparser                                  |
| pydantic           | 2.13.4      | MIT                                  | https://github.com/pydantic/pydantic                                 |
| pydantic-settings  | 2.14.2      | MIT                                  | https://github.com/pydantic/pydantic-settings                        |
| pydantic_core      | 2.46.4      | MIT                                  | https://github.com/pydantic                                          |
| python-dateutil    | 2.9.0.post0 | Apache Software License; BSD License | https://github.com/dateutil/dateutil                                 |
| python-dotenv      | 1.2.2       | BSD-3-Clause                         | https://github.com/theskumar/python-dotenv                           |
| python-multipart   | 0.0.32      | Apache-2.0                           | https://github.com/Kludex/python-multipart                           |
| redis              | 6.4.0       | MIT                                  | https://github.com/redis/redis-py                                    |
| requests           | 2.34.2      | Apache Software License              | https://github.com/psf/requests                                      |
| selectolax         | 0.4.10      | MIT                                  | https://github.com/rushter/selectolax                                |
| six                | 1.17.0      | MIT License                          | https://github.com/benjaminp/six                                     |
| starlette          | 1.3.1       | BSD-3-Clause                         | https://github.com/Kludex/starlette                                  |
| stripe             | 15.3.0      | MIT License                          | https://stripe.com/                                                  |
| typing-inspection  | 0.4.2       | MIT                                  | https://github.com/pydantic/typing-inspection                        |
| typing_extensions  | 4.16.0      | PSF-2.0                              | https://github.com/python/typing_extensions                          |
| tzdata             | 2026.2      | Apache-2.0                           | https://github.com/python/tzdata                                     |
| tzlocal            | 5.4.4       | MIT                                  | https://github.com/regebro/tzlocal/blob/master/CHANGES.txt           |
| urllib3            | 2.7.0       | MIT                                  | https://github.com/urllib3/urllib3/blob/main/CHANGES.rst             |
| uvicorn            | 0.51.0      | BSD-3-Clause                         | https://uvicorn.dev/                                                 |
| uvloop             | 0.22.1      | Apache Software License; MIT License | UNKNOWN                                                              |
| vine               | 5.1.0       | BSD License                          | https://github.com/celery/vine                                       |
| watchfiles         | 1.2.0       | MIT License                          | https://github.com/samuelcolvin/watchfiles                           |
| websockets         | 16.0        | BSD-3-Clause                         | https://github.com/python-websockets/websockets                      |

## Backend worker extras (`backend/requirements-playwright.txt`)

Additional packages installed only on the Playwright worker image (beyond the
runtime lock above).

| Name | Version | License | URL |
|------|---------|---------|-----|
| playwright         | 1.61.0      | Apache-2.0                           | https://github.com/Microsoft/playwright-python                       |
| pyee               | 13.0.1      | MIT License                          | https://github.com/jfhbrook/pyee                                     |

## Frontend production (`frontend/package.json` dependencies)

npm production dependencies and their transitive packages, as resolved in
`frontend/node_modules` for the SPA build.

```
├─ @remix-run/router@1.23.3
│  ├─ licenses: MIT
│  ├─ repository: https://github.com/remix-run/react-router
│  ├─ publisher: Remix Software
│  ├─ email: hello@remix.run
│  ├─ path: node_modules/@remix-run/router
│  └─ licenseFile: node_modules/@remix-run/router/LICENSE.md
├─ @tanstack/query-core@5.101.2
│  ├─ licenses: MIT
│  ├─ repository: https://github.com/TanStack/query
│  ├─ publisher: tannerlinsley
│  ├─ path: node_modules/@tanstack/query-core
│  └─ licenseFile: node_modules/@tanstack/query-core/LICENSE
├─ @tanstack/react-query@5.101.2
│  ├─ licenses: MIT
│  ├─ repository: https://github.com/TanStack/query
│  ├─ publisher: tannerlinsley
│  ├─ path: node_modules/@tanstack/react-query
│  └─ licenseFile: node_modules/@tanstack/react-query/LICENSE
├─ js-tokens@4.0.0
│  ├─ licenses: MIT
│  ├─ repository: https://github.com/lydell/js-tokens
│  ├─ publisher: Simon Lydell
│  ├─ path: node_modules/js-tokens
│  └─ licenseFile: node_modules/js-tokens/LICENSE
├─ loose-envify@1.4.0
│  ├─ licenses: MIT
│  ├─ repository: https://github.com/zertosh/loose-envify
│  ├─ publisher: Andres Suarez
│  ├─ email: zertosh@gmail.com
│  ├─ path: node_modules/loose-envify
│  └─ licenseFile: node_modules/loose-envify/LICENSE
├─ react-dom@18.3.1
│  ├─ licenses: MIT
│  ├─ repository: https://github.com/facebook/react
│  ├─ path: node_modules/react-dom
│  └─ licenseFile: node_modules/react-dom/LICENSE
├─ react-router-dom@6.30.4
│  ├─ licenses: MIT
│  ├─ repository: https://github.com/remix-run/react-router
│  ├─ publisher: Remix Software
│  ├─ email: hello@remix.run
│  ├─ path: node_modules/react-router-dom
│  └─ licenseFile: node_modules/react-router-dom/LICENSE.md
├─ react-router@6.30.4
│  ├─ licenses: MIT
│  ├─ repository: https://github.com/remix-run/react-router
│  ├─ publisher: Remix Software
│  ├─ email: hello@remix.run
│  ├─ path: node_modules/react-router
│  └─ licenseFile: node_modules/react-router/LICENSE.md
├─ react@18.3.1
│  ├─ licenses: MIT
│  ├─ repository: https://github.com/facebook/react
│  ├─ path: node_modules/react
│  └─ licenseFile: node_modules/react/LICENSE
└─ scheduler@0.23.2
   ├─ licenses: MIT
   ├─ repository: https://github.com/facebook/react
   ├─ path: node_modules/scheduler
   └─ licenseFile: node_modules/scheduler/LICENSE
```

---

This file is copied into backend and frontend container images at
`/app/THIRD_PARTY_LICENSES.md` (backend) and served as
`/THIRD_PARTY_LICENSES.md` from the SPA (frontend `public/`).
