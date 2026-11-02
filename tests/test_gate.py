import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from gate import decide, mentions

T = "@optiq-bot"
R = "o/r"


def go(name, event, allowed=frozenset(), pr_head=lambda n: ("optiq/issue-7", R), perm="write"):
    return decide(name, event, T, set(allowed), R, pr_head, lambda login: perm)[0]


def issue_event(body="@optiq-bot fix it", assoc="OWNER", login="alice", kind="User"):
    return {"issue": {"number": 7, "body": body, "author_association": assoc},
            "sender": {"login": login, "type": kind}}


def comment_event(body="@optiq-bot fix it", assoc="MEMBER", login="alice", kind="User", on_pr=False):
    issue = {"number": 9, **({"pull_request": {}} if on_pr else {})}
    return {"issue": issue, "comment": {"body": body, "author_association": assoc},
            "sender": {"login": login, "type": kind}}


def review_event(state="changes_requested", assoc="MEMBER", kind="User", ref="optiq/issue-7", head=R):
    return {"review": {"state": state, "author_association": assoc},
            "pull_request": {"head": {"ref": ref, "repo": {"full_name": head}}},
            "sender": {"login": "alice", "type": kind}}


def ci_event(conclusion="failure", branch="optiq/issue-7", head=R, event="pull_request"):
    return {"workflow_run": {"conclusion": conclusion, "head_branch": branch, "event": event,
                             "head_repository": {"full_name": head}}, "sender": {"type": "User"}}


def test_mention_is_a_whole_word():
    assert mentions("please @optiq-bot fix", T)
    assert mentions("@OPTIQ-BOT fix", T)
    assert not mentions("@optiq-bots fix", T)
    assert not mentions("@optiq-bot-2 fix", T)
    assert not mentions("foo@optiq-bot.com", T)
    assert not mentions(None, T)


def test_quoting_a_request_is_not_a_request():
    assert not mentions("> @optiq-bot fix it\n\nthanks", T)


def test_trusted_people_start_a_run_on_their_issue():
    for assoc in ("OWNER", "MEMBER", "COLLABORATOR"):
        assert go("issues", issue_event(assoc=assoc)) == "7"
        assert go("issue_comment", comment_event(assoc=assoc)) == "9"


def test_strangers_do_not_unless_listed():
    assert go("issues", issue_event(assoc="NONE")) is None
    assert go("issue_comment", comment_event(assoc="CONTRIBUTOR")) is None
    assert go("issues", issue_event(assoc="NONE", login="Alice"), {"alice"}) == "7"


def test_a_read_only_collaborator_or_member_does_not():
    for perm in ("read", "triage", "none"):
        assert go("issues", issue_event(assoc="COLLABORATOR"), perm=perm) is None
        assert go("issue_comment", comment_event(assoc="MEMBER"), perm=perm) is None
        assert go("pull_request_review", review_event(assoc="COLLABORATOR"), perm=perm) is None
    for perm in ("write", "maintain", "admin"):
        assert go("issues", issue_event(assoc="COLLABORATOR"), perm=perm) == "7"


def test_bots_never_start_a_run():
    assert go("issues", issue_event(kind="Bot"), {"alice"}) is None
    assert go("pull_request_review", review_event(kind="Bot")) is None


def test_no_mention_no_run():
    assert go("issues", issue_event(body="just a bug")) is None
    assert go("issue_comment", comment_event(body="thanks", on_pr=True)) is None
    assert go("push", {}) is None


def test_comment_on_its_own_pull_request_belongs_to_the_issue():
    assert go("issue_comment", comment_event(on_pr=True)) == "7"
    assert go("issue_comment", comment_event(on_pr=True), pr_head=lambda n: ("optiq/issue-7-12", R)) == "7"


def test_comment_on_another_pull_request_starts_nothing():
    assert go("issue_comment", comment_event(on_pr=True), pr_head=lambda n: ("feature", R)) is None
    assert go("issue_comment", comment_event(on_pr=True), pr_head=lambda n: ("optiq/issue-7", "evil/r")) is None


def test_a_strangers_comment_never_looks_up_the_pull_request():
    def boom(n):
        raise AssertionError("asked GitHub for a stranger")
    assert go("issue_comment", comment_event(on_pr=True, assoc="NONE"), pr_head=boom) is None


def test_review_needs_no_mention_but_a_trusted_reviewer():
    assert go("pull_request_review", review_event()) == "7"
    assert go("pull_request_review", review_event(state="commented")) == "7"
    assert go("pull_request_review", review_event(state="approved")) is None
    assert go("pull_request_review", review_event(assoc="NONE")) is None


def test_review_of_a_fork_or_another_branch_starts_nothing():
    assert go("pull_request_review", review_event(head="evil/r")) is None
    assert go("pull_request_review", review_event(ref="feature")) is None


def test_ci_only_on_a_failure_of_its_own_branch():
    assert go("workflow_run", ci_event()) == "7"
    assert go("workflow_run", ci_event(conclusion="success")) is None
    assert go("workflow_run", ci_event(branch="feature")) is None
    assert go("workflow_run", ci_event(head="evil/r")) is None
    assert go("workflow_run", ci_event(event="issues")) is None
