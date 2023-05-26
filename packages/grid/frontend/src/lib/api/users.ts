import { getUserIdFromStorage } from './keys';
import { makeSyftUID, syftCall } from './syft-api-call';

export async function getAllUsers() {
  return await syftCall({ path: 'user.get_all', payload: {} });
}

export async function getUser(uid: string) {
  return await syftCall({ path: 'user.view', payload: { uid: makeSyftUID(uid) } });
}

export async function getSelf() {
  return await syftCall({
    path: 'user.view',
    payload: { uid: makeSyftUID(getUserIdFromStorage()) }
  });
}

export async function searchUsersByName(
  name: string,
  chunk_size: number = 0,
  chunk_index: number = 0
) {
  return await syftCall({
    path: 'user.search',
    payload: {
      user_search: { name: name, fqn: 'syft.service.user.user.UserSearch' },
      chunk_size: chunk_size,
      chunk_index: chunk_index
    }
  });
}
