# create-pr

現在branchの変更を必要な検証・文書同期の後にcommitし、日本語のPRを提出する。commit権限とmessage形式はglobal指示の共通契約に従う。Issueの初回実装は`issue-to-pr`、レビュー・修正の進行は明示依頼時の`review-remediation-harness`が担当する。

## 共通契約

- PR提出依頼は、今回scopeのcommit・push・PR作成と、現在repositoryの解決済みremoteへの必要なfetchを含む。別repositoryや別remote、tag、実サービス操作へ許可を広げない。Mergeはユーザーが行う。
- 無関係な整形・依存更新・別課題を混ぜない。Commitは目的ごとに分け、各commitは単独checkout時にもbuild、型check、関連testが通る状態を保つ。同じ目的の実装と関連testは原則として同じcommitに含め、必要な文書も同じ単位で更新する。
- `git add <path>`または`git add -p`で対象を明示してstageし、`git diff --cached`を確認する。Commit件名はglobal規約に従う日本語、PR title・本文も日本語とする。
- PRには`07130918`をassigneeに設定し、内容に合う既存labelを付ける。Copilotのレビュー依頼とmergeはユーザーが行う。
- 必須確認の失敗、未実施、未解決blockerがある状態では完了扱いにしない。`--no-verify`やforce pushで迂回しない。
- Hook等で対象が変わった場合は、その影響を確認してから提出する。結果不明のpush・PR操作はremote/PRを読み直し、成否が不明なまま重複実行しない。

## 呼び出し方

通常依頼では以下の準備から提出まで続ける。呼び出し元で検証・文書同期・レビューが済んでいれば、対応する対象と結果を受け取り、有効なものを再利用する。独立レビューを済ませていない通常提出で、その保証を主張しない。

必要なら`prepare_candidate` (準備・commit) と`publish_exact_candidate` (同じcommitの提出) に分けて呼べる。これは手順の分担名であり、新しいrunnerやJSON artifactを要求するものではない。提出済みかどうかを呼び出し元と共有し、二重にPRを作らない。

## prepare_candidate

### 1. 対象を確認する

1. BranchとGit状態を確認する。main/develop、detached HEADでは編集・commitせず、許可済みの作業branchを用意する。無関係な未commit変更を混ぜない。
2. Repositoryとremote URLを照合する。Baseは明示値、なければremote default、解決できなければdevelop、mainの順に調べる。
3. `git ls-remote`等で対象refを確認し、`git -c maintenance.auto=false fetch --no-tags <remote> refs/heads/<base>:refs/remotes/<remote>/<base>`で選択したbaseだけを取得する。別refやtagをまとめて更新しない。
4. 比較元のfull SHA、HEAD、index・working tree・untrackedを確認する。以前の確認からbaseや対象が変わっていれば、影響する検証・レビューへ戻る。
5. 秘密情報や対象外ファイルをstageしない。

### 2. 必要な確認を終える

AGENTS.md、CI、manifest、Makefileから変更に必要なlint、format、型check、testを解決する。不具合修正やUI変更は必要な実環境確認も行う。`sync-docs-code`の`PASS`または`UPDATED`と関連検証の成功を確認する。

同じコード内容・要件・規約・依存関係・設定・環境へ適用できる成功結果は再利用する。内容不変のcommitだけで一式やり直さない。commit情報に依存する試験、プロジェクトが最終候補で要求する検証、影響を判断できない結果は再実行する。影響のある修正後は文書同期・レビューも必要な範囲で確認する。

ハーネスから独立レビュー済みの候補を受け取った場合、対応する結果を参照する。新しい修正が入ればハーネスへ影響範囲の確認を戻し、旧結果だけで提出しない。

### 3. Commitを作成する

1. 目的ごとのcommit単位を決め、明示pathをstageする。
2. `git diff --cached --check`とstage内容を確認して、日本語件名でcommitする。
3. Commit前の検証対象とcommit後の内容の対応を確認する。Hook等による内容変更があれば必要な検証・レビューを行う。
4. PR対象の変更がすべてcommitされ、working treeとindexがcleanであることを確認する。
5. Repository、branch、base ref/full SHA、候補のfull SHA、有効な検証・文書同期・レビュー結果への参照を呼び出し元へ返す。

この段階ではpushしない。独立レビューをこの段階の後に行う運用でも、有効な既存検証を一式繰り返す必要はない。

## publish_exact_candidate

入力はrepository、許可済みremote、base/head refとfull SHA、scope、提出権限、有効な確認結果。ハーネス経路では独立最終レビューも含む。ここではfile編集、stage、commit、amend、rebase、mergeを行わない。

1. 提出権限と対象repository/remoteを再確認し、準備時のbase refだけを同じ方法でfetchする。
2. ローカルHEAD・作業branch先端が候補SHAと一致し、working tree/indexがcleanで、取得したbaseが確認済みbase SHAと一致することを確認する。
3. Remoteの同名headを読む。候補と同じならpushを省略する。存在しない、または候補のancestorならexact候補SHAをsourceにしてnon-force pushする。remoteが先行・分岐している場合は上書きせず相談する。
4. Push後のremote headを読み直し、候補SHAとの一致を確認する。
5. 対象repositoryのbase/headでopen PRを探す。なければ作成し、あれば依頼範囲のtitle・本文・assignee・labelを更新する。Closed/merged PRは自動再利用しない。
6. PR templateがあれば構造を維持し、全差分に基づいて日本語の本文を作る。完了したIssueだけclose keywordを使う。
7. PR URL、state、draft、assignee、label、base/head ref・SHAを読み直し、対象と一致することを確認する。

照合不一致があれば、追加の提出操作を止めて期待値・観測値・既に行った外部操作を報告する。変更が元の許可内なら準備へ戻り、影響する検証・レビューを終えて新しい候補で提出する。仕様や追加権限が必要な場合だけ相談する。旧runの作り直しは要求しない。

## PR本文と完了報告

```markdown
## 概要

<具体的な問題と変更後の挙動>

## 変更内容

- <主要な変更>

## 動作確認

- <実行commandと結果、再利用結果と対象、未検証事項>

## ドキュメント同期

- status: PASS | UPDATED
- 確認した契約: <対象>
- 更新文書: <path、または更新不要の理由>
- 検証: <結果>

## レビュー観点

- <独立レビューの結果や重点確認箇所>
```

PR URL、検証・レビュー結果、残る制限、次の作業を報告する。認証・環境の問題で提出できなければ完了とせず、完了済みcommitと再開に必要な具体操作を伝える。Push後にPR作成だけが失敗した場合はremoteを照合し、提出から再開できる情報を残す。
