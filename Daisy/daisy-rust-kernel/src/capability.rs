#![allow(dead_code)]
use alloc::collections::BTreeMap;
use alloc::vec::Vec;
use bitflags::bitflags;

bitflags! {
    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub struct Perms: u32 {
        const SEND    = 0b00000001;
        const RECV    = 0b00000010;
        const READ    = 0b00000100;
        const WRITE   = 0b00001000;
        const CREATE  = 0b00010000;
        const DESTROY = 0b00100000;
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ResType {
    Task,
    Endpoint,
    Memory,
    Irq,
}

#[derive(Clone, Debug)]
pub struct Capability {
    pub id: u64,
    pub res_type: ResType,
    pub res_id: u64,
    pub perms: Perms,
    pub owner: u64,
}

pub struct CapabilitySystem {
    caps: BTreeMap<u64, Capability>,
    task_caps: BTreeMap<u64, Vec<u64>>,
    next_id: u64,
}

impl CapabilitySystem {
    pub fn new() -> Self {
        Self {
            caps: BTreeMap::new(),
            task_caps: BTreeMap::new(),
            next_id: 1,
        }
    }

    pub fn grant(&mut self, owner: u64, res_type: ResType, res_id: u64, perms: Perms) -> u64 {
        let id = self.next_id;
        self.next_id += 1;
        let cap = Capability { id, res_type, res_id, perms, owner };
        self.caps.insert(id, cap);
        self.task_caps.entry(owner).or_default().push(id);
        id
    }

    pub fn check(&self, task_id: u64, res_type: ResType, res_id: u64, perm: Perms) -> bool {
        if let Some(cap_ids) = self.task_caps.get(&task_id) {
            for &cid in cap_ids {
                if let Some(cap) = self.caps.get(&cid) {
                    if cap.res_type == res_type && cap.res_id == res_id && cap.perms.contains(perm) {
                        return true;
                    }
                }
            }
        }
        false
    }

    pub fn copy_cap(&mut self, cap_id: u64, new_owner: u64) -> Option<u64> {
        let (rt, rid, perms) = {
            let c = self.caps.get(&cap_id)?;
            (c.res_type, c.res_id, c.perms)
        };
        Some(self.grant(new_owner, rt, rid, perms))
    }

    pub fn revoke(&mut self, cap_id: u64) {
        if let Some(cap) = self.caps.remove(&cap_id) {
            if let Some(list) = self.task_caps.get_mut(&cap.owner) {
                list.retain(|&id| id != cap_id);
            }
        }
    }

    pub fn revoke_all(&mut self, task_id: u64) {
        if let Some(cap_ids) = self.task_caps.remove(&task_id) {
            for id in cap_ids {
                self.caps.remove(&id);
            }
        }
    }
}
