"""Argument role derivation from English voice and dependency relation."""


def argument_role(relation, voice, transitive):
    if relation == "by_phrase":
        return "agent"
    if voice == "passive" and relation == "subject":
        return "patient"
    if voice == "active" and transitive and relation == "subject":
        return "agent"
    if voice == "active" and transitive and relation == "object":
        return "patient"
    return "other"
