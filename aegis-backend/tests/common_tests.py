def yield_test():
    print("Hello Before Yield")
    yield  1
    print("Hello After Yield 1")
    yield 2
    print("Hello After Yield 2")
    yield 3
    print("Hello After Yield 3")
    yield "end"
    print("Hello After Yield 4")


if __name__ == "__main__":
    yield_func = yield_test()
    print(next(yield_func))
    print(next(yield_func))
    print(next(yield_func))
    print(next(yield_func))
    print(next(yield_func))