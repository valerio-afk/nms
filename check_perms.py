from nms_shared.enums import UserPermissions
from typing import List

def check_permission(user:dict,perm:UserPermissions) -> bool:
    user_permissions = user.get("permissions",[])

    if "*" in user_permissions:
        return True

    parts = perm.value.split(".")

    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in user_permissions:
            return True

        wildcard = candidate + ".*"
        if wildcard in user_permissions:
            return True

    return False

def collapse_permissions(user_permissions:List[str], all_permissions:List[str]) -> List[str]:
    def build_nested(perms):
        root = {}
        for perm in perms:
            node = root
            for part in perm.split("."):
                node = node.setdefault(part, {})
        return root

    all_tree = build_nested(all_permissions)
    user_tree = build_nested(user_permissions)

    # special case: user has everything
    if set(user_permissions) == set(all_permissions):
        return ["*"]

    result = []

    def reduce(all_node, user_node, path):

        # if user does not have this branch
        if user_node is None:
            return False

        # leaf node
        if not all_node:
            result.append(".".join(path))
            return True

        all_owned = True

        for key, child in all_node.items():
            owned = reduce(
                child,
                user_node.get(key) if user_node else None,
                path + [key]
            )
            if not owned:
                all_owned = False

        if all_owned:
            prefix = ".".join(path)

            # remove children (collapse)
            result[:] = [
                r for r in result
                if not r.startswith(prefix + ".")
            ]

            result.append(prefix + ".*")
            return True

        return False

    for key, child in all_tree.items():
        reduce(child, user_tree.get(key), [key])

    return sorted(set(result))

user = {
"permissions": [
                "client.dashboard.access",
                "client.dashboard.advanced",
                "network.ddns.manage",
                "pool.conf.create",
                "pool.conf.destroy",
                "pool.conf.expand",
                "pool.conf.format",
                "pool.conf.import"
            ],
}

all_perms = [p.value for p in UserPermissions]

print(collapse_permissions(user['permissions'],all_perms))