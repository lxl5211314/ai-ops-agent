# sample-bug-project

示例含缺陷项目：`get_user_token` 使用 `user['token']` 直接下标访问，
当字典缺少 `token` 键时抛出 `KeyError: 'token'`。

期望补丁：改为 `user.get('token', '')` 安全取值。
