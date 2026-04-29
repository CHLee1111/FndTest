# Issue LLM Review Action for FndTest

Target repository: [CHLee1111/FndTest](https://github.com/CHLee1111/FndTest/)

GitHub issue가 생성, 수정, 재오픈될 때 OpenAI Responses API로 issue 내용을 검토하고 같은 issue에 리뷰 댓글을 작성하는 GitHub Action입니다.

## GitHub 설정

[FndTest Actions secrets/settings](https://github.com/CHLee1111/FndTest/settings/secrets/actions)에서 다음 값을 추가합니다.

- `Secrets`
  - `OPENAI_API_KEY`: OpenAI API key
- `Variables` 선택 사항
  - `OPENAI_MODEL`: 사용할 모델 ID. 기본값은 `gpt-4.1-mini`
  - `REVIEW_TRIGGER_LABEL`: 이 라벨이 붙은 issue만 리뷰하고 싶을 때 설정

## 추가된 파일

- `.github/workflows/issue-review.yml`
  - `issues` 이벤트의 `opened`, `edited`, `reopened`에서 실행됩니다.
  - `workflow_dispatch`로 issue 번호를 넣어 수동 실행할 수 있습니다.
- `.github/scripts/review_issue.py`
  - issue 제목, 본문, 라벨을 읽습니다.
  - OpenAI Responses API에 리뷰를 요청합니다.
  - 기존 LLM 리뷰 댓글이 있으면 업데이트하고, 없으면 새 댓글을 작성합니다.

## 동작 확인

1. 이 파일들을 `CHLee1111/FndTest` repo에 push합니다.
2. `OPENAI_API_KEY` secret을 등록합니다.
3. 새 issue를 생성하거나, [Actions 탭](https://github.com/CHLee1111/FndTest/actions/workflows/issue-review.yml)에서 `Issue LLM Review` workflow를 수동 실행합니다.

workflow는 `TARGET_REPOSITORY=CHLee1111/FndTest`로 설정되어 있어 다른 repo에서 실행되면 명확한 오류를 내고 중단합니다.

## 권한

workflow는 issue 댓글 작성을 위해 `issues: write` 권한을 사용합니다.
