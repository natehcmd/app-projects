#![allow(dead_code)]
use alloc::collections::{BTreeMap, VecDeque};
use alloc::vec::Vec;

pub const MAX_MSG_SIZE: usize = 4096;

#[derive(Clone, Debug)]
pub struct Message {
    pub sender: u64,
    pub msg_type: u8, // 0=call, 1=reply, 2=notification
    pub payload: Vec<u8>,
    pub caps: Vec<u64>,
}

pub struct Endpoint {
    pub id: u64,
    pub name: [u8; 32],
    pub owner: u64,
    pub queue: VecDeque<Message>,
    pub max_queue: usize,
}

pub struct IPCSystem {
    endpoints: BTreeMap<u64, Endpoint>,
    next_id: u64,
}

impl Default for IPCSystem {
    fn default() -> Self { Self::new() }
}

impl IPCSystem {
    pub fn new() -> Self {
        Self { endpoints: BTreeMap::new(), next_id: 0 }
    }

    pub fn create_endpoint(&mut self, owner: u64, name: &[u8]) -> u64 {
        let id = self.next_id;
        self.next_id += 1;
        let mut ep_name = [0u8; 32];
        let len = name.len().min(32);
        ep_name[..len].copy_from_slice(&name[..len]);
        self.endpoints.insert(id, Endpoint {
            id, name: ep_name, owner,
            queue: VecDeque::new(), max_queue: 64,
        });
        id
    }

    pub fn send(&mut self, endpoint_id: u64, msg: Message) -> Result<(), &'static str> {
        let ep = self.endpoints.get_mut(&endpoint_id).ok_or("endpoint not found")?;
        if ep.queue.len() >= ep.max_queue {
            return Err("queue full");
        }
        if msg.payload.len() > MAX_MSG_SIZE {
            return Err("message too large");
        }
        ep.queue.push_back(msg);
        Ok(())
    }

    pub fn recv(&mut self, endpoint_id: u64) -> Option<Message> {
        let ep = self.endpoints.get_mut(&endpoint_id)?;
        ep.queue.pop_front()
    }

    pub fn destroy_endpoint(&mut self, id: u64) {
        self.endpoints.remove(&id);
    }

    pub fn endpoint_owner(&self, id: u64) -> Option<u64> {
        self.endpoints.get(&id).map(|ep| ep.owner)
    }
}
