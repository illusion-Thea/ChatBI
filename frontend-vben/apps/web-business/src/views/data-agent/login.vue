<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { Alert, Button, Card, Input } from 'ant-design-vue';
import { api, session, updateMenus } from './client';
const username=ref('');const password=ref('');const error=ref('');const busy=ref(false);const router=useRouter();
async function login(){busy.value=true;error.value='';try{const data=await api('/auth/login',{method:'POST',body:JSON.stringify({username:username.value,password:password.value})});session.user=data.user;session.csrf=data.csrf_token;updateMenus();await router.replace('/overview');}catch(e){error.value=e instanceof Error?e.message:'登录失败';}finally{busy.value=false;}}
</script>
<template><main class="flex min-h-screen items-center justify-center bg-muted p-5"><Card title="QueryX · 企业数据平台" style="width:420px;max-width:100%"><p class="mb-6 text-muted-foreground">使用内部账号登录</p><Alert v-if="error" class="mb-4" :message="error" type="error" show-icon /><form @submit.prevent="login"><label for="username" class="mb-2 block">账号</label><Input id="username" v-model:value="username" autocomplete="username" :maxlength="64" class="mb-4" /><label for="password" class="mb-2 block">密码</label><Input.Password id="password" v-model:value="password" autocomplete="current-password" :maxlength="256" class="mb-6" /><Button type="primary" html-type="submit" block :loading="busy" :disabled="!username || !password">登录</Button></form><p class="mt-5 text-xs text-muted-foreground">仅限授权员工访问。查询与管理操作会被记录。</p></Card></main></template>
