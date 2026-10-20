# Counter-reading data sources

Large source archives and extracted dictionaries are local-only and ignored by Git. Checksums are
filled after download so the dataset set can be reproduced exactly.

Downloaded and archive-tested on 2026-07-23. UniDic and Open JTalk are extracted beside `raw/`;
the BCCWJ TSV files remain compressed and will be read directly from their ZIP archives.

| Dataset | Version | Local file | Source | License / usage |
|---|---|---|---|---|
| UniDic for Contemporary Written Japanese | 2025-12 | `raw/unidic-cwj-202512.zip` | `https://clrd.ninjal.ac.jp/unidic_archive/2512/unidic-cwj-202512.zip` | UniDic bundled license files; free-license distribution is GPL/LGPL/BSD triple-licensed |
| Open JTalk UTF-8 dictionary | 1.11 | `raw/open_jtalk_dic_utf_8-1.11.tar.gz` | `https://github.com/r9y9/open_jtalk/releases/download/v1.11.1/open_jtalk_dic_utf_8-1.11.tar.gz` | Modified BSD; see archive license files |
| BCCWJ short-unit frequency list | 1.0 | `raw/BCCWJ_frequencylist_suw_ver1_0.zip` | `https://repository.ninjal.ac.jp/record/3234/files/BCCWJ_frequencylist_suw_ver1_0.zip` | Free for research and educational use; see bundled documentation |
| BCCWJ full long-unit frequency list | 1.0 | `raw/BCCWJ_frequencylist_luw_ver1_0.zip` | `https://repository.ninjal.ac.jp/record/3228/files/BCCWJ_frequencylist_luw_ver1_0.zip` | Free for research and educational use; see bundled documentation |

## SHA-256

```text
d94216b589d15d05c408ed59abc5259086703ebbac14e225b5314e4cd106c4db  unidic-cwj-202512.zip
fe6ba0e43542cef98339abdffd903e062008ea170b04e7e2a35da805902f382a  open_jtalk_dic_utf_8-1.11.tar.gz
4e082faa51bedb77b69003358b55278c6736fd32124fc38a93b1b125c64834ba  BCCWJ_frequencylist_suw_ver1_0.zip
0a23e56283187ed4f65d70b89919e05652470474855e1d35566d4039ecb7973a  BCCWJ_frequencylist_luw_ver1_0.zip
```

Machine-readable copies with paths relative to this directory are in `SHA256SUMS`.
