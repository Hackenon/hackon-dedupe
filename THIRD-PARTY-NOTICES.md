# Third-party notices

**HackOn Photo & Video DeDupe** bundles the open-source libraries listed below.
Each is distributed under its own licence. **All of these licences are permissive
and allow commercial use.** The full text of each licence family follows the list.

ffprobe (from FFmpeg) is *not* bundled: the app downloads an official **LGPL** build
on request (Setup → GET FFMPEG) and keeps its licence and notice beside the binary
(`docs/ffmpeg-bundling.md`).

---

## Bundled libraries

| Library | Version | Licence | Copyright | Project |
|---|---|---|---|---|
| Flask | 3.1.3 | BSD-3-Clause | Copyright 2010 Pallets | <https://flask.palletsprojects.com/> |
| Werkzeug | 3.1.9 | BSD-3-Clause | Copyright 2007 Pallets | <https://werkzeug.palletsprojects.com/> |
| Jinja2 | 3.1.6 | BSD-3-Clause | Copyright 2007 Pallets | <https://jinja.palletsprojects.com/> |
| MarkupSafe | 3.0.4 | BSD-3-Clause | Copyright 2010 Pallets | <https://markupsafe.palletsprojects.com/> |
| Click | 8.5.1 | BSD-3-Clause | Copyright 2014 Pallets | <https://click.palletsprojects.com/> |
| ItsDangerous | 2.2.0 | BSD-3-Clause | Copyright 2011 Pallets | <https://itsdangerous.palletsprojects.com/> |
| Blinker | 1.9.0 | MIT | Copyright 2010 Jason Kirtland | <https://blinker.readthedocs.io/> |
| Waitress | 3.0.2 | ZPL-2.1 | Copyright (c) Agendaless Consulting and Contributors | <https://github.com/Pylons/waitress> |
| Pillow | 13.0.0 | HPND (MIT-CMU) | Copyright © 1997-2011 by Secret Labs AB | <https://python-pillow.github.io/> |
| pillow-heif | 1.8.1 | BSD-3-Clause | Copyright (c) 2021-2023, Pillow-Heif contributors. | <https://github.com/bigcat88/pillow_heif> |
| ImageHash | 4.3.2 | BSD-2-Clause | Copyright (c) 2013-2022, Johannes Buchner | <https://github.com/JohannesBuchner/imagehash> |
| NumPy | 2.5.5 | BSD-3-Clause | Copyright (c) 2005-2025, NumPy Developers. | <https://numpy.org/> |
| SciPy | 1.18.1 | BSD-3-Clause | Copyright (c) 2001-2002 Enthought, Inc. 2003, SciPy Developers. | <https://scipy.org/> |
| PyWavelets | 1.10.0 | MIT | Copyright (c) 2006-2012 Filip Wasilewski; (c) The PyWavelets Developers | <https://pywavelets.readthedocs.io/> |
| keyring | 25.7.0 | MIT | Copyright (c) Jason R. Coombs and contributors | <https://github.com/jaraco/keyring> |

> Pillow, NumPy, SciPy and pillow-heif also bundle native components (image codecs,
> libheif, BLAS, …). **libheif** inside pillow-heif is **LGPL-3.0**; the rest are
> permissive. Each package ships those components' full licences in its own
> `licenses/` directory.

---

## Licence texts

### BSD 3-Clause License
*Applies to: Flask, Werkzeug, Jinja2, MarkupSafe, Click, ItsDangerous, pillow-heif, NumPy, SciPy — copyright holders as listed above.*

```
Copyright 2010 Pallets

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

1.  Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

2.  Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

3.  Neither the name of the copyright holder nor the names of its
    contributors may be used to endorse or promote products derived from
    this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### BSD 2-Clause License
*Applies to: ImageHash — copyright holders as listed above.*

```
Copyright (c) 2013-2022, Johannes Buchner
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### MIT License
*Applies to: Blinker, PyWavelets, keyring — copyright holders as listed above.*

```
MIT License

Copyright (c) <year> <copyright holder, as listed in the table above>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Historical Permission Notice and Disclaimer (HPND / MIT-CMU)
*Applies to: Pillow — copyright holders as listed above.*

```
Permission to use, copy, modify, and distribute this software and its
documentation for any purpose and without fee is hereby granted, provided
that the above copyright notice appear in all copies and that both that
copyright notice and this permission notice appear in supporting
documentation, and that the name of the copyright holder not be used in
advertising or publicity pertaining to distribution of the software without
specific, written prior permission.

THE COPYRIGHT HOLDER DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT
SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY SPECIAL, INDIRECT OR
CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE,
DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
OF THIS SOFTWARE.
```

### Zope Public License (ZPL) 2.1
*Applies to: Waitress — copyright holders as listed above.*

```
Zope Public License (ZPL) Version 2.1

A copyright notice accompanies this license document that identifies the
copyright holders.

This license has been certified as open source. It has also been designated as
GPL compatible by the Free Software Foundation (FSF).

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions in source code must retain the accompanying copyright
notice, this list of conditions, and the following disclaimer.

2. Redistributions in binary form must reproduce the accompanying copyright
notice, this list of conditions, and the following disclaimer in the
documentation and/or other materials provided with the distribution.

3. Names of the copyright holders must not be used to endorse or promote
products derived from this software without prior written permission from the
copyright holders.

4. The right to distribute this software or to use it for any purpose does not
give you the right to use Servicemarks (sm) or Trademarks (tm) of the
copyright
holders. Use of them is covered by separate agreement with the copyright
holders.

5. If any files are modified, you must cause the modified files to carry
prominent notices stating that you changed the files and the date of any
change.

Disclaimer

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY EXPRESSED
OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
EVENT SHALL THE COPYRIGHT HOLDERS BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

