# =============================================================================
# Smoke tests for the crashtest package
#
# This script validates the core functionality of crashtest — a Python library
# for inspecting exceptions, walking stack frames, and providing actionable
# solutions for errors.
#
# What is tested:
#   - Package version
#   - Frame: wrapping inspect.FrameInfo, properties (lineno, filename,
#     function, line, file_content), equality, hashing, repr
#   - FrameCollection: construction, repetition tracking (is_repeated,
#     increment_count), and the compact() deduplication algorithm
#   - Inspector: exception introspection (name, message), traceback frame
#     extraction, frame caching, and chained exception support (__context__)
#   - Solution contracts: Solution, ProvidesSolution, HasSolutionsForException,
#     SolutionProviderRepository — all raise NotImplementedError by design
#   - BaseSolution: concrete Solution implementation with title, description,
#     and documentation links
#   - SolutionProviderRepository (concrete): provider registration (single,
#     multiple, via constructor), solution lookup, exception-as-Solution,
#     exception-with-ProvidesSolution, graceful handling of broken providers,
#     and skipping of non-provider classes
# =============================================================================

import inspect
import sys
import traceback

import crashtest
from crashtest.frame import Frame
from crashtest.frame_collection import FrameCollection
from crashtest.inspector import Inspector
from crashtest.contracts.solution import Solution
from crashtest.contracts.base_solution import BaseSolution
from crashtest.contracts.provides_solution import ProvidesSolution
from crashtest.contracts.has_solutions_for_exception import HasSolutionsForException
from crashtest.contracts.solution_provider_repository import (
    SolutionProviderRepository as BaseSolutionProviderRepository,
)
from crashtest.solution_providers.solution_provider_repository import (
    SolutionProviderRepository,
)


def _make_frame_info():
    """Capture a real FrameInfo from the current call stack."""
    stack = inspect.stack()
    return stack[0]


def _raise_and_catch(exc_class, message="test error"):
    """Raise an exception and return it with traceback attached."""
    try:
        raise exc_class(message)
    except exc_class:
        return sys.exc_info()[1]


def _raise_chained():
    """Raise a chained exception and return the outer one."""
    try:
        try:
            raise ValueError("original")
        except ValueError:
            raise RuntimeError("chained") from None
    except RuntimeError:
        return sys.exc_info()[1]


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
def test_version():
    assert crashtest.__version__ == "0.4.1"
    print("OK test_version")


# ---------------------------------------------------------------------------
# Frame
# ---------------------------------------------------------------------------
def test_frame_properties():
    fi = _make_frame_info()
    frame = Frame(fi)
    assert frame.lineno == fi.lineno
    assert frame.filename == fi.filename
    assert frame.function == fi.function
    assert isinstance(frame.line, str)
    assert isinstance(frame.file_content, str)
    assert len(frame.file_content) > 0
    print("OK test_frame_properties")


def test_frame_eq_and_hash():
    fi = _make_frame_info()
    f1 = Frame(fi)
    f2 = Frame(fi)
    assert f1 == f2
    assert hash(f1) == hash(f2)
    print("OK test_frame_eq_and_hash")


def test_frame_repr():
    fi = _make_frame_info()
    frame = Frame(fi)
    r = repr(frame)
    assert r.startswith("<Frame ")
    assert frame.filename in r
    print("OK test_frame_repr")


# ---------------------------------------------------------------------------
# FrameCollection
# ---------------------------------------------------------------------------
def test_frame_collection_defaults():
    fc = FrameCollection()
    assert len(fc) == 0
    assert fc.is_repeated() is False
    assert fc.repetitions == -1
    print("OK test_frame_collection_defaults")


def test_frame_collection_with_frames():
    fi = _make_frame_info()
    frames = [Frame(fi)]
    fc = FrameCollection(frames)
    assert len(fc) == 1
    print("OK test_frame_collection_with_frames")


def test_frame_collection_increment():
    fc = FrameCollection(count=1)
    assert fc.is_repeated() is False
    fc.increment_count()
    assert fc.is_repeated() is True
    assert fc.repetitions == 1
    fc.increment_count(3)
    assert fc.repetitions == 4
    print("OK test_frame_collection_increment")


def test_frame_collection_compact_no_duplicates():
    frames = []
    for s in inspect.stack()[:3]:
        frames.append(Frame(s))
    fc = FrameCollection(frames)
    compacted = fc.compact()
    assert isinstance(compacted, list)
    assert all(isinstance(c, FrameCollection) for c in compacted)
    print("OK test_frame_collection_compact_no_duplicates")


# ---------------------------------------------------------------------------
# Inspector
# ---------------------------------------------------------------------------
def test_inspector_basic():
    exc = _raise_and_catch(ValueError, "boom")
    insp = Inspector(exc)
    assert insp.exception is exc
    assert insp.exception_name == "ValueError"
    assert insp.exception_message == "boom"
    assert insp.has_previous_exception() is False
    assert insp.previous_exception is None
    print("OK test_inspector_basic")


def test_inspector_frames():
    exc = _raise_and_catch(RuntimeError, "frame test")
    insp = Inspector(exc)
    frames = insp.frames
    assert isinstance(frames, FrameCollection)
    assert len(frames) > 0
    f = frames[0]
    assert isinstance(f, Frame)
    assert f.function == "_raise_and_catch"
    print("OK test_inspector_frames")


def test_inspector_frames_cached():
    exc = _raise_and_catch(TypeError)
    insp = Inspector(exc)
    assert insp.frames is insp.frames
    print("OK test_inspector_frames_cached")


def test_inspector_chained_exception():
    exc = _raise_chained()
    insp = Inspector(exc)
    assert insp.exception_name == "RuntimeError"
    assert insp.has_previous_exception() is True
    prev = insp.previous_exception
    assert isinstance(prev, ValueError)
    print("OK test_inspector_chained_exception")


# ---------------------------------------------------------------------------
# Solution contract & BaseSolution
# ---------------------------------------------------------------------------
def test_solution_contract_raises():
    s = Solution()
    for prop in ("solution_title", "solution_description", "documentation_links"):
        try:
            getattr(s, prop)
            assert False, f"{prop} should raise"
        except NotImplementedError:
            pass
    print("OK test_solution_contract_raises")


def test_base_solution():
    sol = BaseSolution(title="Fix it", description="Do this")
    assert sol.solution_title == "Fix it"
    assert sol.solution_description == "Do this"
    assert sol.documentation_links == []
    print("OK test_base_solution")


def test_base_solution_defaults():
    sol = BaseSolution()
    assert sol.solution_title == ""
    assert sol.solution_description == ""
    print("OK test_base_solution_defaults")


# ---------------------------------------------------------------------------
# ProvidesSolution contract
# ---------------------------------------------------------------------------
def test_provides_solution_contract():
    ps = ProvidesSolution()
    try:
        ps.solution
        assert False, "should raise"
    except NotImplementedError:
        pass
    print("OK test_provides_solution_contract")


# ---------------------------------------------------------------------------
# HasSolutionsForException contract
# ---------------------------------------------------------------------------
def test_has_solutions_contract():
    h = HasSolutionsForException()
    try:
        h.can_solve(Exception())
        assert False, "should raise"
    except NotImplementedError:
        pass
    try:
        h.get_solutions(Exception())
        assert False, "should raise"
    except NotImplementedError:
        pass
    print("OK test_has_solutions_contract")


# ---------------------------------------------------------------------------
# SolutionProviderRepository contract
# ---------------------------------------------------------------------------
def test_repository_contract():
    repo = BaseSolutionProviderRepository()
    for method, args in [
        ("register_solution_provider", (object,)),
        ("register_solution_providers", ([],)),
        ("get_solutions_for_exception", (Exception(),)),
    ]:
        try:
            getattr(repo, method)(*args)
            assert False, f"{method} should raise"
        except NotImplementedError:
            pass
    print("OK test_repository_contract")


# ---------------------------------------------------------------------------
# SolutionProviderRepository (concrete)
# ---------------------------------------------------------------------------
def test_repository_empty():
    repo = SolutionProviderRepository()
    solutions = repo.get_solutions_for_exception(Exception("x"))
    assert solutions == []
    print("OK test_repository_empty")


def test_repository_register_single():
    class MyProvider(HasSolutionsForException):
        def can_solve(self, exception):
            return isinstance(exception, ValueError)

        def get_solutions(self, exception):
            return [BaseSolution(title="val fix", description="handle value")]

    repo = SolutionProviderRepository()
    result = repo.register_solution_provider(MyProvider)
    assert result is repo

    solutions = repo.get_solutions_for_exception(ValueError("bad"))
    assert len(solutions) == 1
    assert solutions[0].solution_title == "val fix"

    solutions = repo.get_solutions_for_exception(TypeError("nope"))
    assert len(solutions) == 0
    print("OK test_repository_register_single")


def test_repository_register_multiple():
    class ProviderA(HasSolutionsForException):
        def can_solve(self, exception):
            return True

        def get_solutions(self, exception):
            return [BaseSolution(title="A")]

    class ProviderB(HasSolutionsForException):
        def can_solve(self, exception):
            return True

        def get_solutions(self, exception):
            return [BaseSolution(title="B")]

    repo = SolutionProviderRepository()
    result = repo.register_solution_providers([ProviderA, ProviderB])
    assert result is repo

    solutions = repo.get_solutions_for_exception(Exception("x"))
    titles = [s.solution_title for s in solutions]
    assert "A" in titles
    assert "B" in titles
    print("OK test_repository_register_multiple")


def test_repository_constructor_with_providers():
    class Prov(HasSolutionsForException):
        def can_solve(self, exception):
            return True

        def get_solutions(self, exception):
            return [BaseSolution(title="init")]

    repo = SolutionProviderRepository(solution_providers=[Prov])
    solutions = repo.get_solutions_for_exception(Exception("x"))
    assert len(solutions) == 1
    assert solutions[0].solution_title == "init"
    print("OK test_repository_constructor_with_providers")


def test_repository_exception_is_solution():
    class SolutionException(Exception, Solution):
        @property
        def solution_title(self):
            return "self-solving"

        @property
        def solution_description(self):
            return "I am the solution"

        @property
        def documentation_links(self):
            return ["https://example.com"]

    exc = SolutionException("oops")
    repo = SolutionProviderRepository()
    solutions = repo.get_solutions_for_exception(exc)
    assert len(solutions) == 1
    assert solutions[0].solution_title == "self-solving"
    assert solutions[0].documentation_links == ["https://example.com"]
    print("OK test_repository_exception_is_solution")


def test_repository_exception_provides_solution():
    class SolvableException(Exception, ProvidesSolution):
        @property
        def solution(self):
            return BaseSolution(title="provided", description="from exception")

    exc = SolvableException("oops")
    repo = SolutionProviderRepository()
    solutions = repo.get_solutions_for_exception(exc)
    assert len(solutions) == 1
    assert solutions[0].solution_title == "provided"
    print("OK test_repository_exception_provides_solution")


def test_repository_provider_can_solve_raises():
    class BadProvider(HasSolutionsForException):
        def can_solve(self, exception):
            raise RuntimeError("broken")

        def get_solutions(self, exception):
            return [BaseSolution(title="never")]

    repo = SolutionProviderRepository([BadProvider])
    solutions = repo.get_solutions_for_exception(Exception("x"))
    assert len(solutions) == 0
    print("OK test_repository_provider_can_solve_raises")


def test_repository_provider_get_solutions_raises():
    class BadProvider(HasSolutionsForException):
        def can_solve(self, exception):
            return True

        def get_solutions(self, exception):
            raise RuntimeError("broken")

    repo = SolutionProviderRepository([BadProvider])
    solutions = repo.get_solutions_for_exception(Exception("x"))
    assert len(solutions) == 0
    print("OK test_repository_provider_get_solutions_raises")


def test_repository_skips_non_provider():
    class NotAProvider:
        pass

    repo = SolutionProviderRepository([NotAProvider])
    solutions = repo.get_solutions_for_exception(Exception("x"))
    assert len(solutions) == 0
    print("OK test_repository_skips_non_provider")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception:
            failed += 1
            print(f"FAIL {test_fn.__name__}")
            traceback.print_exc()

    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")
    if failed:
        sys.exit(1)
