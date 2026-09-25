/* api() returns the server's {error: ...} body instead of throwing, so a refused
   request looked like success to pages that used try/catch (a 409 "build already
   running" read as started; a 400 duel polled id=undefined). apiOk throws. */
window.apiOk = async (p, body) => {
  const r = await api(p, body);
  if (r && typeof r === "object" && !Array.isArray(r) && r.error) throw new Error(r.error);
  return r;
};
